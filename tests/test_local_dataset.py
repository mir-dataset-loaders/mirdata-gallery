"""Local mode (--local): the stats of the fake dataset, read from its folder on disk.

Every expected number comes from the table in fake_dataset.py.
"""

import mirdata
from mirdata import annotations

import card_fields
import fake_dataset
from fake_dataset import DATA_HOME
from stats import dataset


def test_fake_dataset_loads_in_mirdata(fake_mirdata):
    ds = mirdata.initialize("fake_dataset", data_home=DATA_HOME)
    assert ds.track_ids == ["track1", "track2", "track3"]
    missing, invalid = ds.validate(verbose=False)
    assert not missing["tracks"] and not invalid["tracks"]
    assert isinstance(ds.track("track1").beats, annotations.BeatData)
    assert ds.track("track3").chords is None


def test_audio_stats_are_correct(fake_mirdata):
    audio = dataset.compute("fake_dataset", DATA_HOME, local=True)["audio"]
    assert audio["status"] == "ok"
    assert audio["problems"] == []
    assert audio["errors"] == {}
    assert audio["n_tracks"] == 3
    assert audio["n_tracks_counted"] == 3
    assert audio["total_seconds"] == 7.0
    assert audio["sample_rates"] == {8000: 2, 16000: 1}
    assert audio["sample_rate"] is None  # the files do not share one rate
    assert audio["duration_histogram"]["unit"] == "s"
    assert sum(audio["duration_histogram"]["counts"]) == 3


def test_annotation_stats_are_correct(fake_mirdata):
    result = dataset.compute("fake_dataset", DATA_HOME, local=True)["annotations"]
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
    assert beats["beats_per_bar"] == {3: 1, 4: 2}
    tempo = beats["tempo"]  # 120, 60 and 240 bpm
    assert tempo["unit"] == "bpm"
    assert sum(tempo["counts"]) == 3
    assert tempo["edges"][0] <= 60 and tempo["edges"][-1] >= 240
    assert set(beats) == {"type", "n_tracks", "n_annotations", "tempo", "beats_per_bar"}

    chords = result["annotations"]["chords"]
    assert chords["type"] == "ChordData"
    assert chords["n_tracks"] == 2
    assert chords["n_annotations"] == 2
    assert chords["labels"] == {"C:maj": 2, "A:min": 1, "G:7": 1, "N": 1}
    assert chords["qualities"] == {"maj": 2, "min": 1, "7": 1, "N": 1}
    assert set(chords) == {"type", "n_tracks", "n_annotations", "labels", "qualities"}


def test_annotation_types_match_the_dataset(fake_mirdata):
    """The card and the stats have exactly the dataset's annotation types: none missing, none extra."""
    ds = mirdata.initialize("fake_dataset", data_home=DATA_HOME)
    result = dataset.compute("fake_dataset", DATA_HOME, local=True)["annotations"]
    dataset_types = ["BeatData", "ChordData"]  # beats, chords (fake_dataset.py)
    assert card_fields.annotations(ds) == dataset_types
    assert sorted(entry["type"] for entry in result["annotations"].values()) == dataset_types
    assert sorted(result["tracks_with"]) == dataset_types


def test_error_only_for_the_part_that_crashes(fake_mirdata, monkeypatch):
    """A loader bug that breaks the annotations part: that part is an error, the audio is still computed."""

    def broken(self):
        raise RuntimeError("loader bug")

    monkeypatch.setattr(fake_dataset.Dataset, "track_ids", property(broken))
    result = dataset.compute("fake_dataset", DATA_HOME, local=True)
    assert result["annotations"]["status"] == "error"
    assert "loader bug" in result["annotations"]["error"]
    assert result["audio"]["status"] == "ok"
    assert result["audio"]["total_seconds"] == 7.0


def test_error_when_local_copy_is_missing(fake_mirdata, tmp_path):
    result = dataset.compute("fake_dataset", str(tmp_path / "nowhere"), local=True)
    assert set(result) == {"name", "error"}
