"""scripts/card_builder.py: the card's fields, built from the fake dataset."""

import mirdata
import pytest

import fake_dataset_loader
from card_builder import annotation_properties, annotations, build_card, clean_text
from fake_dataset_loader import DATA_HOME

FIELDS = [
    "name",
    "license",
    "annotations",
    "bibtex",
    "summary",
    "docstring_hash",
    "stats",
]


@pytest.fixture
def ds(fake_mirdata):
    return mirdata.initialize("fake_dataset", data_home=DATA_HOME)


def test_build_card(ds):
    stats = {"computed": {"mode": "local", "index": "abc123"}}
    card = build_card(ds, summary="Three tracks.", docstring_hash="d0c", stats=stats)
    assert list(card) == FIELDS, "fields should come in card order"
    assert card["name"] == "fake_dataset", "name should be the dataset's name"
    license_info, bibtex = fake_dataset_loader.LICENSE_INFO, fake_dataset_loader.BIBTEX
    assert card["license"] == license_info, "license should come from the loader"
    assert card["bibtex"] == bibtex, "bibtex should come from the loader"
    types = ["BeatData", "ChordData"]
    assert card["annotations"] == types, "annotations should list the Track's types"
    assert card["summary"] == "Three tracks.", "summary should be passed through"
    assert card["docstring_hash"] == "d0c", "docstring_hash should be passed through"
    assert card["stats"] is stats, "stats should be passed through"

    empty = build_card(ds)
    given = [empty["summary"], empty["docstring_hash"], empty["stats"]]
    assert given == [None] * 3, "summary, hash and stats should be None when not given"


def test_annotations(ds):
    types = ["BeatData", "ChordData"]
    assert (
        annotations(ds) == types
    ), "annotations should list the Track's annotation types, sorted"
    ds.name = "fake_genre"
    with_genre = types + ["Genre"]
    assert annotations(ds) == with_genre, "a *_genre dataset should also get Genre"
    found = annotations(ds)
    assert (
        "NoteData" not in found
    ), "a type the Track does not have should not be listed"


def test_annotation_properties(ds):
    found = annotation_properties(ds)
    expected = {"beats": "BeatData", "chords": "ChordData"}
    assert found == expected, (
        "a property hinted with an annotation type should be found; one hinted as"
        " something else, with no keyword in its name, should not"
    )


def test_annotation_properties_guess(ds, monkeypatch):
    # no return hint, and "melody" in its name makes it a guessed F0Data
    flag = property(lambda self: False)
    monkeypatch.setattr(
        fake_dataset_loader.Track, "alternating_melody", flag, raising=False
    )
    found = annotation_properties(ds)
    assert (
        found["alternating_melody"] == "F0Data"
    ), "a property without a hint should be guessed from a keyword in its name"
    declared = annotation_properties(ds, guess=False)
    expected = {"beats": "BeatData", "chords": "ChordData"}
    assert (
        declared == expected
    ), "guess=False should keep only the properties typed by their hint"


def test_clean_text():
    text = "\n\n    @misc{fake,   \n      title={Fake}\n    }  \n\n"
    expected = "@misc{fake,\n  title={Fake}\n}"
    assert clean_text(text) == expected, (
        "trailing spaces, the common indentation and the blank lines around"
        " should be removed"
    )
    assert clean_text(None) is None, "None should pass through"
