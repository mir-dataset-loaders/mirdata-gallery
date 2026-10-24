"""card_builder.py: the card fields of the fake dataset."""

import mirdata

import card_builder
from fake_dataset import DATA_HOME
from stats import compute


def test_annotation_types_match_the_dataset(fake_mirdata):
    """The card and the stats have exactly the dataset's annotation types: none missing, none extra."""
    ds = mirdata.initialize("fake_dataset", data_home=DATA_HOME)
    result = compute("fake_dataset", DATA_HOME, local=True)["annotations"]
    dataset_types = ["BeatData", "ChordData"]  # beats, chords (fake_dataset.py)
    assert card_builder.annotations(ds) == dataset_types
    assert sorted(entry["type"] for entry in result["annotations"].values()) == dataset_types
    assert sorted(result["tracks_with"]) == dataset_types
