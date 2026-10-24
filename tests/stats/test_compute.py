"""compute() (stats/__init__.py) on the fake dataset: local mode, read from its folder on disk,
and remote mode, read from its zips on a local server (conftest.py, fake_remotes).

Every expected number comes from the table in fake_dataset.py. A remote run must
give exactly the numbers of a local run.
"""

import mirdata
from mirdata import annotations

import fake_dataset
from fake_dataset import DATA_HOME
from stats import compute


def test_fake_dataset_loads_in_mirdata(fake_mirdata):
    ds = mirdata.initialize("fake_dataset", data_home=DATA_HOME)
    assert ds.track_ids == ["track1", "track2", "track3"]
    missing, invalid = ds.validate(verbose=False)
    assert not missing["tracks"] and not invalid["tracks"]
    assert isinstance(ds.track("track1").beats, annotations.BeatData)
    assert ds.track("track3").chords is None


def test_audio_stats_are_counted_from_the_index(fake_mirdata):
    audio = compute("fake_dataset", DATA_HOME, local=True)["audio"]
    assert audio == {"status": "ok", "problems": [], "n_tracks": 3, "n_audio_files": 3}


def test_limit_does_not_change_the_audio_counts(fake_mirdata):
    """--limit cuts the annotation tracks; the audio counts always cover the whole index."""
    result = compute("fake_dataset", DATA_HOME, local=True, limit=1)
    assert result["audio"] == {"status": "ok", "problems": [], "n_tracks": 3, "n_audio_files": 3}
    assert result["annotations"]["n_tracks_loaded"] == 1


def test_annotation_stats_are_correct(fake_mirdata):
    result = compute("fake_dataset", DATA_HOME, local=True)["annotations"]
    assert result["status"] == "ok"
    assert result["problems"] == []
    assert result["errors"] == {}
    assert result["annotation_errors"] == {}
    assert result["skipped"] == {}
    assert result["n_tracks"] == 3
    assert result["n_tracks_loaded"] == 3
    assert result["tracks_with"] == {"BeatData": 3, "ChordData": 2}
    assert set(result["annotations"]) == {"beats", "chords"}

    beats = result["annotations"]["beats"]
    assert beats["type"] == "BeatData"
    assert beats["n_tracks"] == 3
    assert beats["n_annotations"] == 3
    assert beats["meter"] == {3: 1, 4: 2}
    tempo = beats["tempo_from_beats"]  # 120, 60 and 240 bpm
    assert tempo["unit"] == "bpm"
    assert sum(tempo["counts"]) == 3
    assert tempo["edges"][0] <= 60 and tempo["edges"][-1] >= 240
    assert set(beats) == {"type", "n_tracks", "n_annotations", "tempo_from_beats", "meter"}

    chords = result["annotations"]["chords"]
    assert chords["type"] == "ChordData"
    assert chords["n_tracks"] == 2
    assert chords["n_annotations"] == 2
    assert chords["labels"] == {"C:maj": 2, "A:min": 1, "G:7": 1, "N": 1}
    assert chords["qualities"] == {"maj": 2, "min": 1, "7": 1, "N": 1}
    assert set(chords) == {"type", "n_tracks", "n_annotations", "labels", "qualities"}


def test_error_only_for_the_part_that_crashes(fake_mirdata, monkeypatch):
    """A loader bug that breaks the annotations part: that part is an error, the audio is still counted."""

    def broken(self):
        raise RuntimeError("loader bug")

    monkeypatch.setattr(fake_dataset.Dataset, "track_ids", property(broken))
    result = compute("fake_dataset", DATA_HOME, local=True)
    assert result["annotations"]["status"] == "error"
    assert "loader bug" in result["annotations"]["error"]
    assert result["audio"] == {"status": "ok", "problems": [], "n_tracks": 3, "n_audio_files": 3}


def test_error_when_local_copy_is_missing(fake_mirdata, tmp_path):
    result = compute("fake_dataset", str(tmp_path / "nowhere"), local=True)
    assert set(result) == {"name", "error"}


# ---------------------------------------------------------------- remote mode


def without_sources(part):
    """A part's result without its log lines, which name where the files came from."""
    return {k: v for k, v in part.items() if k != "sources"}


def test_remote_stats_equal_local_stats(fake_remotes, tmp_path):
    remote = compute("fake_dataset", str(tmp_path))
    local = compute("fake_dataset", DATA_HOME, local=True)
    for part in ("audio", "annotations"):
        assert remote[part]["status"] == "ok"
        assert without_sources(remote[part]) == without_sources(local[part])


def test_audio_part_sends_no_request(fake_remotes, tmp_path):
    """The audio part counts the index: the server is never asked for audio.zip or anything else."""
    audio = compute("fake_dataset", str(tmp_path), parts=["audio"])["audio"]
    assert audio == {"status": "ok", "problems": [], "n_tracks": 3, "n_audio_files": 3}
    assert fake_remotes.requests == []
