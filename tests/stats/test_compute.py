"""compute() in local mode, on the fake dataset.

Every expected number comes from the table in tests/fake_dataset_loader.py.
"""

import shutil

import mirdata

import fake_dataset_loader
from fake_dataset_loader import DATA_HOME
import stats
from stats import compute
from stats.annotation_types import grid
from stats.annotations import collect_stats_candidates, drop_excluded_names


def compute_local(data_home=DATA_HOME, **kwargs):
    return compute("fake_dataset", str(data_home), local=True, **kwargs)


def copy_dataset(tmp_path):
    """A copy of the fake dataset, for a test to break."""
    data_home = tmp_path / "fake_dataset"
    shutil.copytree(DATA_HOME, data_home)
    return data_home


def test_compute(fake_mirdata):
    result = compute_local()
    parts = {"name", "audio", "annotations"}
    assert set(result) == parts, "result should have the dataset name and both parts"
    assert result["name"] == "fake_dataset", "result name should be the dataset's name"

    audio = result["audio"]
    assert audio["status"] == "ok", "audio status should be ok when the index loads"
    assert audio["problems"] == [], "audio should report no problems"
    assert audio["n_tracks"] == 3, "audio should count every track in the index"
    assert (
        audio["n_audio_files"] == 3
    ), "audio should count every audio file in the index"

    ann = result["annotations"]
    assert (
        ann["status"] == "ok"
    ), "annotations status should be ok when every annotation is read"
    assert ann["problems"] == [], "a local run should report no problems"
    assert ann["n_tracks"] == 3, "annotations should count every track in the dataset"
    assert (
        ann["n_tracks_loaded"] == 3
    ), "n_tracks_loaded should count the tracks that load"
    tracks_with = {"BeatData": 3, "ChordData": 2}
    assert (
        ann["tracks_with"] == tracks_with
    ), "each type should count only the tracks that have it"
    assert ann["errors"] == {}, "errors should list only the tracks that fail to load"
    assert (
        ann["annotation_errors"] == {}
    ), "annotation_errors should list only the annotations that fail to read"
    assert ann["missing_files"] == {}, "a local run should miss no file"
    assert (
        DATA_HOME in ann["sources"][0]
    ), "sources should name the local copy that was read"
    entries = {"beats", "chords"}
    assert (
        set(ann["annotations"]) == entries
    ), "only annotation properties should get an entry"

    beats = ann["annotations"]["beats"]
    fields = {
        "type",
        "n_tracks",
        "n_annotations",
        "meter",
        "meter_changes",
        "tempo_from_beats",
        "tempo_changes",
    }
    assert set(beats) == fields, (
        "a BeatData entry should have exactly type, n_tracks, n_annotations, meter,"
        " meter_changes, tempo_from_beats and tempo_changes"
    )
    assert (
        beats["type"] == "BeatData"
    ), "an entry's type should come from the property's type hint"
    assert (
        beats["n_tracks"] == 3
    ), "n_tracks should count only the tracks that have the annotation"
    assert beats["n_annotations"] == 3, "n_annotations should count every annotation"
    meter = {3: 1, 4: 2}
    assert beats["meter"] == meter, "meter should count the tracks per beats-per-bar"
    meter_changes = {0: 3}
    assert (
        beats["meter_changes"] == meter_changes
    ), "meter_changes should count the tracks per number of meter changes"
    tempo = grid([80, 120, 240], "bpm")
    assert (
        beats["tempo_from_beats"] == tempo
    ), "tempo should pool one value per track on one 1-bpm grid"
    tempo_changes = {"tempo": [120, 80, 240], "change": [0, 0, 0]}
    assert (
        beats["tempo_changes"] == tempo_changes
    ), "tempo_changes should list each track's tempo and change, in track order"

    chords = ann["annotations"]["chords"]
    fields = {"type", "n_tracks", "n_annotations", "labels", "qualities"}
    assert set(chords) == fields, (
        "a ChordData entry should have exactly type, n_tracks, n_annotations, labels"
        " and qualities"
    )
    assert (
        chords["type"] == "ChordData"
    ), "an entry's type should come from the property's type hint"
    assert (
        chords["n_tracks"] == 2
    ), "n_tracks should count only the tracks that have the annotation"
    assert chords["n_annotations"] == 2, "n_annotations should count every annotation"
    labels = {"C:maj": 2, "A:min": 1, "G:7": 1, "N": 1}
    assert (
        chords["labels"] == labels
    ), "labels should count every chord label of every track"
    qualities = {"maj": 2, "min": 1, "7": 1, "N": 1}
    assert (
        chords["qualities"] == qualities
    ), "qualities should count the quality of every label"


def test_compute_durations(fake_mirdata):
    audio = compute_local()["audio"]
    assert (
        audio["total_seconds"] == 7
    ), "total_seconds should add up the tracks' durations"
    sample_rates = {"8k": 2, "16k": 1}
    assert (
        audio["sample_rates"] == sample_rates
    ), "sample_rates should count the tracks at each rate"
    durations = grid([2, 4, 1], "s")
    assert (
        audio["durations"] == durations
    ), "durations should be the grid of the tracks' durations, in seconds"


def test_compute_audio_error(fake_mirdata, monkeypatch):
    features = {
        "audio_mic": {"duration_seconds": 2.0, "sample_rate": 8000, "num_channels": 1},
        "audio_mix": {"duration_seconds": 2.5, "sample_rate": 8000, "num_channels": 1},
    }
    tracks = {
        "track1": {
            "audio_mic": ["mic.wav", "md5"],
            "audio_mix": ["mix.wav", "md5"],
            "audio_features": features,
        }
    }
    monkeypatch.setattr(stats, "load_index", lambda ds: {"tracks": tracks})
    result = compute_local()
    audio = result["audio"]
    assert (
        audio["status"] == "error"
    ), "audio files that disagree should make the audio part an error"
    assert "track1" in audio["error"], "the error should name the track"
    assert (
        result["annotations"]["status"] == "ok"
    ), "an audio error should not stop the annotations"


def test_compute_parts(fake_mirdata):
    result = compute_local(parts=["audio"])
    parts = {"name", "audio"}
    assert set(result) == parts, "only the parts asked for should be computed"


def test_compute_broken_annotation_file(fake_mirdata, tmp_path):
    data_home = copy_dataset(tmp_path)
    (data_home / "annotations/beats/track2.txt").write_text("not\ta beat\n")
    ann = compute_local(data_home)["annotations"]
    assert (
        ann["status"] == "incomplete"
    ), "a broken annotation file should make the status incomplete"
    failed = set(ann["annotation_errors"])
    assert failed == {
        "beats"
    }, "only the property whose file is broken should get an error"
    beat_errors = ann["annotation_errors"]["beats"]
    assert (
        beat_errors["n_tracks"] == 1
    ), "the error should count the one track whose file is broken"
    assert (
        len(beat_errors["logs"]) == 1
    ), "the broken file should give one error message"
    beats, chords = ann["annotations"]["beats"], ann["annotations"]["chords"]
    assert (
        beats["n_tracks"] == 2
    ), "the broken property should still count the tracks whose files read"
    assert (
        chords["n_tracks"] == 2
    ), "other properties should not be affected by a broken file"
    assert (
        ann["n_tracks_loaded"] == 3
    ), "a broken annotation file should not stop its track from loading"


def test_compute_track_error(fake_mirdata, monkeypatch):
    build = fake_dataset_loader.Track.__init__

    def build_all_but_track2(self, track_id, *args):
        if track_id == "track2":
            raise ValueError("cannot build track2")
        build(self, track_id, *args)

    monkeypatch.setattr(fake_dataset_loader.Track, "__init__", build_all_but_track2)
    ann = compute_local()["annotations"]
    assert (
        ann["status"] == "incomplete"
    ), "a track that fails to load should make the status incomplete"
    failed = set(ann["errors"])
    assert failed == {"track2"}, "the error should name the track that failed"
    assert ann["n_tracks_loaded"] == 2, "the other tracks should still load"
    beats = ann["annotations"]["beats"]
    assert (
        beats["n_tracks"] == 2
    ), "none of the failed track's annotations should be read"


def test_compute_not_an_annotation(fake_mirdata, monkeypatch):
    # chords is hinted ChordData but returns a dict; alternating_melody returns a bool
    def chords_as_a_dict(path):
        return {"labels": ["C:maj"]} if path else None

    monkeypatch.setattr(fake_dataset_loader, "load_chords", chords_as_a_dict)
    flag = property(lambda self: False)
    monkeypatch.setattr(
        fake_dataset_loader.Track, "alternating_melody", flag, raising=False
    )
    ann = compute_local()["annotations"]
    assert set(ann["annotations"]) == {"beats"}, (
        "a name whose first value is not an annotation should get no entry,"
        " whatever its type hint or its name"
    )
    assert ann["annotation_errors"] == {}, "a name dropped for its value is not an error"
    assert ann["status"] == "ok", "a dropped name should not change the status"


def test_compute_without_type_hint(fake_mirdata, monkeypatch):
    # no return hint, and nothing in the name says what it holds
    onsets = property(lambda self: self.beats)
    monkeypatch.setattr(fake_dataset_loader.Track, "onsets", onsets, raising=False)
    ann = compute_local()["annotations"]
    entry = ann["annotations"]["onsets"]
    assert entry["type"] == "BeatData", "the type should come from the value"
    assert entry["n_tracks"] == 3, "the name should be read on every track"


def test_compute_tempo_by_name(fake_mirdata, monkeypatch):
    bpm = {"track1": 120.0, "track2": "80", "track3": "fast"}
    tempo = property(lambda self: bpm[self.track_id])
    monkeypatch.setattr(fake_dataset_loader.Track, "tempo", tempo, raising=False)
    ann = compute_local()["annotations"]
    entry = ann["annotations"]["tempo"]
    assert (
        entry["type"] == "TempoData"
    ), "a plain value under the tempo word should be typed TempoData"
    assert entry["tempo"] == grid(
        [120, 80], "bpm"
    ), "every value that is a number should be read as a bpm"
    assert ann["annotation_errors"] == {
        "tempo": {
            "n_tracks": 1,
            "logs": [
                {
                    "error": "WrongFormat: not a mirdata TempoData object (got str)",
                    "n_tracks": 1,
                }
            ],
        }
    }, "a tempo value that is not a number should be a WrongFormat annotation error"
    assert (
        ann["status"] == "incomplete"
    ), "an unusable tempo value should make the status incomplete"


def test_compute_key_by_name(fake_mirdata, monkeypatch):
    # fma_keys: the key and its mode are two names; da_tacos: an essentia dict
    keys = {"track1": "F#", "track2": "E major | E minor", "track3": {"key": b"C"}}
    modes = {"track1": "Major", "track2": "minor", "track3": "minor"}
    key = property(lambda self: keys[self.track_id])
    mode = property(lambda self: modes[self.track_id])
    monkeypatch.setattr(fake_dataset_loader.Track, "key", key, raising=False)
    monkeypatch.setattr(fake_dataset_loader.Track, "mode", mode, raising=False)
    ann = compute_local()["annotations"]
    entry = ann["annotations"]["key"]
    assert (
        entry["type"] == "KeyData"
    ), "a plain value under the key word should be typed KeyData"
    assert entry["keys"] == {"F#:major": 1, "E:major": 1, "E:minor": 1}, (
        "every key in a string should be read; one without a mode takes the"
        " track's mode"
    )
    assert "mode" not in ann["annotations"], "mode alone should not be read"
    assert ann["annotation_errors"] == {
        "key": {
            "n_tracks": 1,
            "logs": [
                {
                    "error": "WrongFormat: not a mirdata KeyData object (got dict)",
                    "n_tracks": 1,
                }
            ],
        }
    }, "a key value that is not text should be a WrongFormat annotation error"
    assert (
        ann["status"] == "incomplete"
    ), "an unusable key value should make the status incomplete"


def test_compute_errors_held(fake_mirdata, monkeypatch):
    def onsets(self):
        if self.track_id == "track1":
            raise ValueError("broken onsets file")
        if self.track_id == "track3":
            return "not beats"
        return self.beats

    monkeypatch.setattr(
        fake_dataset_loader.Track, "onsets", property(onsets), raising=False
    )
    ann = compute_local()["annotations"]
    assert (
        ann["annotations"]["onsets"]["n_tracks"] == 1
    ), "only the track whose value is an annotation should be read"
    errors = ann["annotation_errors"]["onsets"]
    assert errors == {
        "n_tracks": 2,
        "logs": [
            {"error": "ValueError: broken onsets file", "n_tracks": 1},
            {
                "error": "WrongFormat: not a mirdata BeatData object (got str)",
                "n_tracks": 1,
            },
        ],
    }, (
        "an error held before the name had a type, and a later value that is not"
        " its type, should both be annotation errors"
    )
    assert ann["status"] == "incomplete", "annotation errors should make it incomplete"


def test_compute_never_read(fake_mirdata, monkeypatch):
    def spectrogram(self):
        raise FileNotFoundError("no spectrogram file")

    monkeypatch.setattr(
        fake_dataset_loader.Track, "spectrogram", property(spectrogram), raising=False
    )
    ann = compute_local()["annotations"]
    assert ann["annotation_errors"] == {
        "spectrogram": {
            "n_tracks": 3,
            "logs": [
                {"error": "FileNotFoundError: no spectrogram file", "n_tracks": 3}
            ],
        }
    }, "a name that could not be read on any track should keep each track's error"
    assert (
        ann["status"] == "incomplete"
    ), "a name never read should make the status incomplete"


def test_drop_excluded_names():
    names = [
        "beats",
        "tempo",
        "_track_metadata",
        "audio",
        "audio_mic",
        "Audio_Mix",
        "tempo_path",
        "musicxml_paths",
    ]
    assert drop_excluded_names(names) == ["beats", "tempo"], (
        "private names, names with audio and file paths should be dropped;"
        " the rest kept, sorted"
    )


def test_collect_stats_candidates(fake_mirdata):
    ds = mirdata.initialize("fake_dataset", data_home=DATA_HOME)
    found = collect_stats_candidates(ds.track("track1"))
    assert found == ["beats", "chords", "title", "track_id"], (
        "every property and attribute of the track should be a candidate,"
        " except audio, file paths and private names"
    )


def test_compute_instrument(fake_mirdata, monkeypatch):
    # no return hints: found by the word "instrument" in their names
    labels = property(lambda self: "Gt, Gt, Bs")
    number = property(lambda self: 3)
    monkeypatch.setattr(
        fake_dataset_loader.Track, "live_instrument", labels, raising=False
    )
    monkeypatch.setattr(
        fake_dataset_loader.Track, "instrument_id", number, raising=False
    )
    ann = compute_local()["annotations"]
    expected = {
        "type": "Instrument",
        "n_tracks": 3,
        "n_annotations": 3,
        "instruments": {"Gt": 6, "Bs": 3},
    }
    assert (
        ann["annotations"]["live_instrument"] == expected
    ), "an instrument field should be read on every track, each label counted as listed"
    assert (
        ann["tracks_with"]["Instrument"] == 3
    ), "tracks_with should count the tracks with instrument labels"
    assert ann["annotation_errors"] == {
        "instrument_id": {
            "n_tracks": 3,
            "logs": [
                {"error": "WrongFormat: no instrument labels (got int)", "n_tracks": 3}
            ],
        }
    }, "a number in an instrument field should be a WrongFormat annotation error"
    assert (
        ann["status"] == "incomplete"
    ), "an unusable instrument field should make the status incomplete"


def test_compute_crashing_part(fake_mirdata, monkeypatch):
    def crash(self):
        raise RuntimeError("loader bug")

    monkeypatch.setattr(fake_dataset_loader.Dataset, "track_ids", property(crash))
    result = compute_local()
    ann, audio = result["annotations"], result["audio"]
    assert ann["status"] == "error", "a part that crashes should get status error"
    assert "loader bug" in ann["error"], "the error should say what crashed"
    assert audio["status"] == "ok", "a crash in one part should not stop the other"


def test_compute_errors(fake_mirdata, tmp_path):
    only_error = {"name", "error"}
    result = compute_local(tmp_path / "nowhere")
    assert (
        set(result) == only_error
    ), "a missing local copy should give only the name and an error"
    result = compute("no_such_dataset", str(tmp_path), local=True)
    assert (
        set(result) == only_error
    ), "an unknown dataset should give only the name and an error"


def test_compute_local_never_contacts_remotes(fake_remotes):
    compute_local()
    assert (
        fake_remotes.requests == []
    ), "a local run should send no request to the remotes"
