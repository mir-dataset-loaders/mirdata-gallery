"""compute() in local mode, on the fake dataset.

Every expected number comes from the table in tests/fake_dataset_loader.py.
"""

import shutil

import fake_dataset_loader
from fake_dataset_loader import DATA_HOME
from stats import compute
from stats.histograms import histogram


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
    assert (
        ann["skipped"] == {}
    ), "a property whose values are its type should not be skipped"
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
    fields = {"type", "n_tracks", "n_annotations", "meter", "tempo_from_beats"}
    assert set(beats) == fields, (
        "a BeatData entry should have exactly type, n_tracks, n_annotations, meter"
        " and tempo_from_beats"
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
    tempo = histogram([80, 120, 240], "bpm")
    assert (
        beats["tempo_from_beats"] == tempo
    ), "tempo should pool one value per track into one bpm histogram"

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
    fields = {"total_seconds", "sample_rate", "duration_histogram"}
    missing = fields - set(audio)
    assert not missing, f"audio should have {missing}: the gallery shows the durations"


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
    tracks = set(ann["annotation_errors"]["beats"]["examples"])
    assert tracks == {"track2"}, "the error should name the track whose file is broken"
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


def test_compute_not_mirdata_annotation(fake_mirdata, monkeypatch):
    def chords_as_a_dict(path):
        return {"labels": ["C:maj"]} if path else None

    monkeypatch.setattr(fake_dataset_loader, "load_chords", chords_as_a_dict)
    ann = compute_local()["annotations"]
    tracks = set(ann["annotation_errors"]["chords"]["examples"])
    assert tracks == {"track1", "track2"}, (
        "a value that is not the type its hint names should be an annotation error"
        " for each track that returns one"
    )
    assert (
        "chords" not in ann["annotations"]
    ), "a property with no value of its type should get no annotations entry"
    assert (
        ann["skipped"] == {}
    ), "a property typed by its hint should be reported as an error, not as skipped"
    assert (
        ann["status"] == "incomplete"
    ), "a value that is not the type its hint names should make the status incomplete"


def test_compute_guessed_property(fake_mirdata, monkeypatch):
    # no return hint, and "melody" in its name makes it a guessed F0Data
    flag = property(lambda self: False)
    monkeypatch.setattr(
        fake_dataset_loader.Track, "alternating_melody", flag, raising=False
    )
    ann = compute_local()["annotations"]
    assert (
        "alternating_melody" in ann["skipped"]
    ), "a guessed property that is not an annotation should be reported as skipped"
    assert ann["annotation_errors"] == {}, "a wrong guess from the name is not an error"
    assert ann["status"] == "ok", "a skipped property should not change the status"


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
