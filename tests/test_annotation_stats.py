"""Tests for annotation_types.py (Stat classes) and annotation_stats.py (discovery, results, CLI)."""

import json
import logging
import os
import sys
from collections import Counter
from types import SimpleNamespace
from typing import Optional

import numpy as np
import pytest
from mirdata import annotations as A
from mirdata.annotations import Annotation
from mirdata.core import cached_property

import annotation_fetch
import annotation_stats
import annotation_types
from audio_fakes import FAKE_URL, FakeRangeSession, fake_remote, zip_bytes
from annotation_types import STATS, Beats, Chords, F0, Keys, Notes, Tempo
from histograms import histogram


# ------------------------------------------------------------ test objects


def beats(times=(0.0, 0.5, 1.0, 1.5), positions=(1, 2, 3, 4), unit="s"):
    return A.BeatData(
        np.array(times, dtype=float),
        unit,
        None if positions is None else np.array(positions),
        None if positions is None else "bar_index",
    )


def chords(labels=("C:maj", "A:min7", "N"), intervals=((0.0, 1.0), (1.0, 3.0), (3.0, 3.5))):
    return A.ChordData(np.array(intervals, dtype=float), "s", list(labels), "harte")


def f0(frequencies=(0.0, 220.0, 440.0, 0.0), voicing=(0.0, 1.0, 1.0, 0.0)):
    times = np.arange(len(frequencies)) * 0.01
    return A.F0Data(times, "s", np.array(frequencies), "hz", np.array(voicing), "binary")


def notes(intervals=((0.0, 0.5), (0.5, 2.0)), pitches=(60.0, 72.0), unit="s"):
    return A.NoteData(np.array(intervals, dtype=float), unit, np.array(pitches), "midi")


def tempo(tempos=(120.0, 128.0)):
    intervals = np.array([[30.0 * i, 30.0 * (i + 1)] for i in range(len(tempos))])
    return A.TempoData(intervals, "s", np.array(tempos), "bpm")


class FakeTrack:
    """A Track class with the kinds of properties the discovery has to sort out."""

    def __init__(self, beats=None, chords=None, tempo=None, chords_alt=None):
        self._beats, self._chords, self._tempo = beats, chords, tempo
        self._chords_alt = chords_alt

    @property
    def beats(self) -> Optional[A.BeatData]:  # typed: BeatData
        return self._beats

    @cached_property
    def chords(self) -> Optional[A.ChordData]:  # typed, cached: ChordData
        return self._chords

    @property
    def other_chords(self) -> Optional[A.ChordData]:  # a second ChordData property
        return self._chords_alt

    @property
    def tempo(self):  # keyword rule: TempoData, but the value is a metadata string
        return self._tempo

    @property
    def live_instrument(self):  # keyword rule: Instrument, not an official type
        return "Gt"

    @property
    def title(self):  # plain metadata
        return "a song"

    def not_a_property(self):
        return None


class BrokenTrack(FakeTrack):
    @property
    def beats(self):
        raise IOError("annotation file missing")


def fake_dataset(tracks):
    """A dataset object with just what dataset_stats() touches."""
    return SimpleNamespace(
        _track_class=FakeTrack,
        track_ids=list(tracks),
        track=lambda track_id: tracks[track_id],
    )


# ---------------------------------------------------------------- registry


def test_stats_cover_exactly_the_official_annotation_types():
    official = {cls.__name__ for cls in Annotation.__subclasses__()}
    assert set(STATS) == official
    assert len(STATS) == 10
    for name, stat_class in STATS.items():
        assert stat_class.annotation.__name__ == name


@pytest.mark.parametrize("stat_class", STATS.values(), ids=list(STATS))
def test_add_rejects_anything_but_its_annotation_class(stat_class):
    stat = stat_class()
    wrong = chords() if stat_class is not Chords else beats()
    assert stat.add("135.0") is False
    assert stat.add(wrong) is False
    assert stat.n_tracks == 0


# ------------------------------------------------------------------- stats


def test_beats_per_track_tempo_and_meter():
    stat = Beats()
    assert stat.add(beats()) is True  # 4 beats at 120 bpm, 4/4
    assert stat.add(beats((0.0, 500.0, 1000.0), (1, 2, 3), unit="ms")) is True  # 3/4, in ms
    assert stat.n_tracks == 2
    assert stat.bpm == [120.0, 120.0]
    assert stat.result() == {
        "beats_per_track": histogram([4, 3], "beats"),
        "beats_per_bar": {3: 1, 4: 1},
        "tempo": histogram([120.0, 120.0], "bpm"),
    }


def test_beats_ignore_position_zero_and_missing_positions():
    stat = Beats()
    stat.add(beats((0.0, 0.5, 1.0), (0, 1, 2)))  # 0 marks a beat outside any bar
    stat.add(beats((0.0, 0.5, 1.0), None))
    assert stat.result()["beats_per_bar"] == {2: 1}
    assert stat.n_tracks == 2


def test_beats_in_ticks_give_no_tempo():
    stat = Beats()
    stat.add(beats((0.0, 480.0, 960.0), (1, 2, 3), unit="ticks"))
    assert stat.bpm == []
    assert stat.result()["beats_per_track"] == histogram([3], "beats")
    assert stat.result()["tempo"] is None


def test_chords_labels_qualities_and_lengths():
    stat = Chords()
    stat.add(chords())
    stat.add(A.ChordData(np.array([[0.0, 2.0]]), "s", ["C"], "open"))  # bare root is major
    assert stat.n_tracks == 2
    assert stat.result() == {
        "chords_per_track": histogram([3, 1], "chords"),
        "chord_seconds": histogram([1.0, 2.0, 0.5, 2.0], "s", log=True),
        "n_unique_labels": 4,
        "labels": {"C:maj": 1, "A:min7": 1, "N": 1, "C": 1},
        "qualities": {"maj": 2, "min7": 1, "N": 1},
    }


@pytest.mark.parametrize(
    ("label", "quality"),
    [
        ("C", "maj"),
        ("C:maj", "maj"),
        ("A:min7", "min7"),
        ("G:7/3", "7"),
        ("D:maj(9)", "maj"),
        ("E:", "maj"),
        ("N", "N"),
        ("X", "X"),
    ],
)
def test_chord_quality(label, quality):
    assert annotation_types.chord_quality(label) == quality


def test_f0_voicing_hop_and_range():
    stat = F0()
    stat.add(f0())
    stat.add(f0((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)))  # fully unvoiced track
    assert stat.n_tracks == 2
    assert stat.result() == {
        "hop_seconds": {0.01: 2},
        "voiced_fraction": histogram([0.5, 0.0], "fraction"),
        "f0_median_per_track": histogram([330.0], "hz"),
        "f0_min": 220.0,
        "f0_max": 440.0,
    }


def test_f0_likelihood_voicing_counts_any_positive_value():
    stat = F0()
    stat.add(A.F0Data(
        np.array([0.0, 0.01]), "s", np.array([100.0, 200.0]), "hz",
        np.array([0.3, 0.0]), "likelihood",
    ))
    assert stat.result()["voiced_fraction"] == histogram([0.5], "fraction")
    assert stat.result()["f0_max"] == 100.0


def test_f0_with_nothing_voiced():
    stat = F0()
    stat.add(f0((0.0, 0.0), (0.0, 0.0)))
    result = stat.result()
    assert result["f0_median_per_track"] is None
    assert result["f0_min"] is None


def test_multif0_polyphony():
    stat = STATS["MultiF0Data"]()
    stat.add(A.MultiF0Data(np.array([0.0, 0.01, 0.02]), "s", [[220.0, 330.0], [], [440.0]], "hz"))
    assert stat.result() == {
        "max_polyphony": histogram([2], "voices"),
        "voiced_fraction": histogram([2 / 3], "fraction"),
    }


def test_notes_counts_lengths_and_pitch():
    stat = Notes()
    stat.add(notes())
    assert stat.result() == {
        "notes_per_track": histogram([2], "notes"),
        "note_seconds": histogram([0.5, 1.5], "s", log=True),
        "pitch": histogram([60.0, 72.0], "midi"),
        "pitch_min": 60.0,
        "pitch_max": 72.0,
    }


def test_notes_in_ticks_have_no_lengths():
    stat = Notes()
    stat.add(notes(((0.0, 480.0),), (60.0,), unit="ticks"))
    assert stat.result()["note_seconds"] is None
    assert stat.result()["notes_per_track"] == histogram([1], "notes")


def test_sections_with_and_without_labels():
    stat = STATS["SectionData"]()
    stat.add(A.SectionData(np.array([[0.0, 10.0], [10.0, 25.0]]), "s", ["intro", "verse"], "open"))
    stat.add(A.SectionData(np.array([[0.0, 5.0]]), "s"))
    assert stat.result() == {
        "sections_per_track": histogram([2, 1], "sections"),
        "section_seconds": histogram([10.0, 15.0, 5.0], "s", log=True),
        "n_unique_labels": 2,
        "labels": {"intro": 1, "verse": 1},
    }


def test_keys_and_modes():
    stat = Keys()
    stat.add(A.KeyData(np.array([[0.0, 30.0], [30.0, 60.0]]), "s", ["C:major", "A:minor"], "key_mode"))
    stat.add(A.KeyData(np.array([[0.0, 30.0]]), "s", ["C:major"], "key_mode"))
    assert stat.result() == {
        "keys": {"C:major": 2, "A:minor": 1},
        "modes": {"major": 2, "minor": 1},
    }


def test_lyrics_lines():
    stat = STATS["LyricData"]()
    stat.add(A.LyricData(np.array([[0.0, 1.0], [1.0, 2.0]]), "s", ["hello", "world"], "words"))
    assert stat.result() == {"lines_per_track": histogram([2], "lines")}


def test_events_labels():
    stat = STATS["EventData"]()
    stat.add(A.EventData(np.array([[0.0, 1.0], [2.0, 2.5]]), "s", ["dog", "siren"], "open"))
    stat.add(A.EventData(np.array([[0.0, 1.0]]), "s", ["dog"], "open"))
    assert stat.result() == {
        "events_per_track": histogram([2, 1], "events"),
        "n_unique_labels": 2,
        "labels": {"dog": 2, "siren": 1},
    }


def test_tempo_annotation():
    stat = Tempo()
    stat.add(tempo())
    stat.add(tempo((90.0,)))
    assert stat.n_tracks == 2
    assert stat.result() == {"bpm": histogram([120.0, 128.0, 90.0], "bpm")}


# ----------------------------------------------------------------- helpers


def test_top_counts_folds_the_rest_into_other():
    counter = Counter({f"label{i}": 20 - i for i in range(12)})
    result = annotation_types.top_counts(counter, top=3)
    assert list(result) == ["label0", "label1", "label2", "(other)"]
    assert result["(other)"] == sum(counter.values()) - (20 + 19 + 18)
    assert annotation_types.top_counts(Counter({"a": 1}), top=3) == {"a": 1}


def test_interval_lengths_units():
    seconds = annotation_types.interval_lengths(notes(((0.0, 500.0),), (60.0,), unit="ms"))
    assert seconds.tolist() == [0.5]
    assert annotation_types.interval_lengths(notes(((0.0, 480.0),), (60.0,), unit="ticks")) is None
    assert annotation_types.interval_lengths(chords()).tolist() == [1.0, 2.0, 0.5]


# --------------------------------------------------------------- discovery


def test_annotation_properties_keeps_only_official_types():
    ds = SimpleNamespace(_track_class=FakeTrack)
    assert annotation_stats.annotation_properties(ds) == {
        "beats": "BeatData",
        "chords": "ChordData",
        "other_chords": "ChordData",
        "tempo": "TempoData",
    }


# ------------------------------------------------------------- end to end


def test_dataset_stats_end_to_end():
    ds = fake_dataset(
        {
            "a": FakeTrack(beats=beats(), chords=chords(), tempo="135.0"),
            "b": FakeTrack(beats=beats((0.0, 1.0, 2.0), (1, 2, 3)), chords=None, tempo=""),
            "broken": BrokenTrack(),
        }
    )
    stats = annotation_stats.dataset_stats("fake", ds)

    assert stats["name"] == "fake"
    assert stats["n_tracks"] == 3
    assert stats["n_tracks_loaded"] == 2
    assert list(stats["annotations"]) == ["beats", "chords"]
    assert stats["annotations"]["beats"]["type"] == "BeatData"
    assert stats["annotations"]["beats"]["n_tracks"] == 2
    assert stats["annotations"]["beats"]["tempo"] == histogram([120.0, 60.0], "bpm")
    assert stats["annotations"]["chords"]["type"] == "ChordData"
    assert stats["annotations"]["chords"]["n_tracks"] == 1  # track b has no chords
    assert stats["tracks_with"] == {"BeatData": 2, "ChordData": 1}
    assert stats["skipped"] == {"tempo": "not a mirdata TempoData object (got str)"}
    assert list(stats["errors"]) == ["broken"]
    assert "annotation file missing" in stats["errors"]["broken"]


def test_two_properties_of_one_type_are_reported_separately():
    ds = fake_dataset(
        {
            "a": FakeTrack(chords=chords(), chords_alt=chords(("G:maj",), ((0.0, 1.0),))),
            "b": FakeTrack(chords=chords()),
        }
    )
    stats = annotation_stats.dataset_stats("fake", ds)
    chords_entry = stats["annotations"]["chords"]
    other_entry = stats["annotations"]["other_chords"]
    assert chords_entry["type"] == other_entry["type"] == "ChordData"
    assert chords_entry["n_tracks"] == 2
    assert other_entry["n_tracks"] == 1
    assert other_entry["labels"] == {"G:maj": 1}
    # per type: annotations add up across properties, tracks are counted once
    assert chords_entry["n_tracks"] + other_entry["n_tracks"] == 3
    assert stats["tracks_with"] == {"ChordData": 2}


def test_mirdata_warnings_are_silenced_while_loading(caplog):
    class NoisyTrack(FakeTrack):
        @property
        def beats(self) -> Optional[A.BeatData]:
            logging.warning("solo chords are the same as comp")
            return beats_annotation

    beats_annotation = beats()
    ds = fake_dataset({"a": NoisyTrack()})
    with caplog.at_level(logging.WARNING):
        stats = annotation_stats.dataset_stats("fake", ds)
    assert stats["annotations"]["beats"]["n_tracks"] == 1
    assert "solo chords" not in caplog.text
    logging.warning("after loading")  # logging is restored afterwards
    assert "after loading" in caplog.text


def test_dataset_stats_limit_and_failing_stat(monkeypatch):
    class Boom(Beats):
        def read(self, value):
            raise ValueError("cannot read this")

    monkeypatch.setitem(annotation_types.STATS, "BeatData", Boom)
    ds = fake_dataset({"a": FakeTrack(beats=beats()), "b": FakeTrack(beats=beats())})
    stats = annotation_stats.dataset_stats("fake", ds, limit=1)
    assert stats["n_tracks_loaded"] == 1
    assert stats["annotations"] == {}
    assert stats["skipped"] == {"beats": "ValueError: cannot read this"}


def test_dataset_stats_result_dumps_to_json():
    ds = fake_dataset({"a": FakeTrack(beats=beats(), chords=chords())})
    text = json.dumps(annotation_stats.dataset_stats("fake", ds))
    assert '"type": "BeatData"' in text


def test_print_stats_mentions_sources_and_skips(capsys):
    ds = fake_dataset({"a": FakeTrack(beats=beats(), tempo="135.0")})
    annotation_stats.print_stats(annotation_stats.dataset_stats("fake", ds), limit=None, elapsed=0.1)
    out = capsys.readouterr().out
    assert "beats (BeatData; 1 tracks)" in out
    assert "tracks with:            BeatData: 1" in out
    assert "skipped tempo: not a mirdata TempoData object (got str)" in out


# --------------------------------------------------------------------- CLI


def test_main_json(tmp_path, monkeypatch, capsys):
    (tmp_path / "fake").mkdir()
    ds = fake_dataset({"a": FakeTrack(beats=beats())})
    monkeypatch.setattr(annotation_stats.mirdata, "list_datasets", lambda: ["fake", "other"])
    monkeypatch.setattr(annotation_stats.mirdata, "initialize", lambda name, data_home: ds)
    monkeypatch.setattr(
        sys,
        "argv",
        ["annotation_stats.py", "--dataset", "fake", "--local", "--datasets-dir", str(tmp_path), "--json"],
    )
    annotation_stats.main()
    result = json.loads(capsys.readouterr().out)
    assert list(result) == ["fake"]
    assert result["fake"]["annotations"]["beats"]["tempo"] == histogram([120.0], "bpm")


def test_main_reports_missing_local_copy(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(annotation_stats.mirdata, "list_datasets", lambda: ["fake"])
    monkeypatch.setattr(
        sys, "argv", ["annotation_stats.py", "--local", "--datasets-dir", str(tmp_path), "--json"]
    )
    annotation_stats.main()
    result = json.loads(capsys.readouterr().out)
    assert "no local copy" in result["fake"]["error"]


def test_main_rejects_unknown_dataset(monkeypatch):
    monkeypatch.setattr(annotation_stats.mirdata, "list_datasets", lambda: ["fake"])
    monkeypatch.setattr(sys, "argv", ["annotation_stats.py", "--dataset", "unknown"])
    with pytest.raises(SystemExit, match="Dataset 'unknown' not found"):
        annotation_stats.main()


@pytest.mark.parametrize("limit", ["0", "-1"])
def test_main_rejects_nonpositive_limit(limit, monkeypatch):
    monkeypatch.setattr(annotation_stats.mirdata, "list_datasets", lambda: [])
    monkeypatch.setattr(sys, "argv", ["annotation_stats.py", "--limit", limit])
    with pytest.raises(SystemExit) as exc:
        annotation_stats.main()
    assert exc.value.code == 2


# ------------------------------------------------------------- remote mode


class FileTrack:
    """A track that, like a mirdata Track, reads its beats file from data_home."""

    def __init__(self, data_home, path):
        self.path = os.path.join(data_home, path)

    @property
    def beats(self) -> Optional[A.BeatData]:
        with open(self.path) as f:
            times = [float(line) for line in f if line.strip()]
        return beats(times, list(range(1, len(times) + 1)))


def remote_dataset(tmp_path, data_home):
    """A dataset whose index, remotes and tracks point at a fake zip remote."""
    index = {
        "tracks": {
            "a": {"audio": ["audio/a.wav", "x"], "beats": ["ann/a.txt", "x"]},
            "b": {"audio": ["audio/b.wav", "x"], "beats": ["ann/b.txt", "x"]},
        }
    }
    index_path = tmp_path / "index.json"
    index_path.write_text(json.dumps(index))
    paths = {"a": "ann/a.txt", "b": "ann/b.txt"}
    return SimpleNamespace(
        index_path=str(index_path),
        remotes={"all": fake_remote("all.zip", FAKE_URL)},
        _track_class=FileTrack,
        track_ids=["a", "b"],
        track=lambda track_id: FileTrack(data_home, paths[track_id]),
    )


ARCHIVE = {
    "audio/a.wav": b"RIFF" + b"\0" * 100,
    "ann/a.txt": b"0.0\n0.5\n1.0\n",  # 120 bpm
    "ann/b.txt": b"0.0\n1.0\n2.0\n",  # 60 bpm
}


def test_remote_stats_fetches_annotations_and_computes(tmp_path, monkeypatch):
    session = FakeRangeSession({FAKE_URL: zip_bytes(ARCHIVE)})
    monkeypatch.setattr(annotation_fetch.requests, "Session", lambda: session)
    data_home = str(tmp_path / "fetch" / "fake")
    ds = remote_dataset(tmp_path, data_home)

    stats = annotation_stats.remote_stats("fake", ds, data_home)

    assert stats["annotations"]["beats"]["tempo"] == histogram([120.0, 60.0], "bpm")
    assert stats["n_tracks_loaded"] == 2
    assert stats["errors"] == {}
    assert stats["missing_files"] == {}
    assert "2 matched, 2 fetched" in stats["sources"][0]
    assert not os.path.exists(os.path.join(data_home, "audio"))


def test_remote_stats_reports_missing_files_and_failing_tracks(tmp_path, monkeypatch):
    archive = {k: v for k, v in ARCHIVE.items() if k != "ann/b.txt"}
    session = FakeRangeSession({FAKE_URL: zip_bytes(archive)})
    monkeypatch.setattr(annotation_fetch.requests, "Session", lambda: session)
    data_home = str(tmp_path / "fetch" / "fake")

    stats = annotation_stats.remote_stats("fake", remote_dataset(tmp_path, data_home), data_home)

    assert stats["missing_files"] == {"ann/b.txt": "not in any readable remote"}
    assert stats["annotations"]["beats"]["n_tracks"] == 1
    assert list(stats["errors"]) == ["b"]


def test_remote_stats_limit_fetches_only_those_tracks(tmp_path, monkeypatch):
    session = FakeRangeSession({FAKE_URL: zip_bytes(ARCHIVE)})
    monkeypatch.setattr(annotation_fetch.requests, "Session", lambda: session)
    data_home = str(tmp_path / "fetch" / "fake")

    stats = annotation_stats.remote_stats("fake", remote_dataset(tmp_path, data_home), data_home, limit=1)

    assert os.path.exists(os.path.join(data_home, "ann/a.txt"))
    assert not os.path.exists(os.path.join(data_home, "ann/b.txt"))
    assert stats["n_tracks_loaded"] == 1


def test_main_remote_is_the_default(tmp_path, monkeypatch, capsys):
    session = FakeRangeSession({FAKE_URL: zip_bytes(ARCHIVE)})
    monkeypatch.setattr(annotation_fetch.requests, "Session", lambda: session)
    datasets = {}

    def initialize(name, data_home):
        datasets[name] = remote_dataset(tmp_path, data_home)
        return datasets[name]

    monkeypatch.setattr(annotation_stats.mirdata, "list_datasets", lambda: ["fake"])
    monkeypatch.setattr(annotation_stats.mirdata, "initialize", initialize)
    fetch_dir = tmp_path / "kept"
    monkeypatch.setattr(
        sys, "argv", ["annotation_stats.py", "--dataset", "fake", "--fetch-dir", str(fetch_dir)]
    )
    annotation_stats.main()
    out = capsys.readouterr().out
    assert "2 matched, 2 fetched" in out
    assert "beats (BeatData; 2 tracks)" in out
    assert (fetch_dir / "fake" / "ann" / "a.txt").exists()  # --fetch-dir keeps the files


def test_local_stats_without_local_copy(tmp_path):
    with pytest.raises(FileNotFoundError, match="no local copy"):
        annotation_stats.local_stats("fake", str(tmp_path / "missing"))
