"""scripts/card_builder.py: the card's fields, built from the fake dataset."""

import mirdata
import pytest

import fake_dataset_loader
from card_builder import (
    annotations,
    build_card,
    clean_text,
    tasks,
)
from fake_dataset_loader import DATA_HOME

FIELDS = [
    "name",
    "summary",
    "annotations",
    "tasks",
    "stats",
    "summary_hash",
    "bibtex",
    "license",
]


def stats_with(**types):
    """A card's stats field whose annotation entries have these types: stats_with(beats="BeatData")."""
    entries = {name: {"type": ann_type} for name, ann_type in types.items()}
    return {
        "computed": {"mode": "local", "index": "abc123"},
        "annotations": {"annotations": entries},
    }


# fake_dataset's stats: its beats and chords
STATS = stats_with(beats="BeatData", chords="ChordData")


@pytest.fixture
def ds(fake_mirdata):
    return mirdata.initialize("fake_dataset", data_home=DATA_HOME)


def test_build_card(ds):
    card = build_card(ds, stats=STATS)
    assert list(card) == FIELDS, "fields should come in card order"
    assert card["name"] == "fake_dataset", "name should be the dataset's name"
    license_info, bibtex = fake_dataset_loader.LICENSE_INFO, fake_dataset_loader.BIBTEX
    assert card["license"] == license_info, "license should come from the loader"
    assert card["bibtex"] == bibtex, "bibtex should come from the loader"
    types = ["BeatData", "ChordData"]
    assert card["annotations"] == types, "annotations should list the stats' types"
    found = ["Beat Tracking", "Chord Recognition"]
    assert card["tasks"] == found, "tasks should be those of the stats' types"
    left = [card["summary"], card["summary_hash"]]
    assert left == [None] * 2, "summary and summary_hash are generate_cards' to fill"
    assert card["stats"] is STATS, "stats should be passed through"
    no_stats = build_card(ds)
    assert no_stats["stats"] is None, "stats should be None when not given"
    assert no_stats["annotations"] == [], "no stats should give no annotation types"


def test_annotations():
    types = ["BeatData", "ChordData"]
    assert (
        annotations(STATS) == types
    ), "annotations should list the types of the stats entries, sorted"
    two_chords = stats_with(chords="ChordData", leadsheet_chords="ChordData")
    assert annotations(two_chords) == [
        "ChordData"
    ], "a type with several entries should be listed once"
    no_entries = [
        None,
        {"computed": {}, "error": "loader bug"},
        {"annotations": {"status": "error", "error": "loader bug"}},
        stats_with(),
    ]
    for stats in no_entries:
        assert (
            annotations(stats) == []
        ), f"stats without entries should give no types ({stats})"


def test_tasks(ds):
    found = ["Beat Tracking", "Chord Recognition"]
    assert (
        tasks(ds, STATS) == found
    ), "tasks should be those of the annotation types, sorted"
    lyrics_events = stats_with(
        lyrics="LyricData", events="EventData", matches="EventDataExtended"
    )
    both = ["Lyrics Transcription", "Lyrics-to-Audio Alignment"]
    assert tasks(ds, lyrics_events) == both, (
        "a type with two tasks should add both; EventData and EventDataExtended"
        " should add none"
    )
    assert tasks(ds, None) == [], "no stats should give no tasks"

    ds._multitrack_class = mirdata.core.MultiTrack
    assert tasks(ds, None) == [
        "Source Separation"
    ], "a multitrack loader should add Source Separation, even without stats"


def test_clean_text():
    text = "\n\n    @misc{fake,   \n      title={Fake}\n    }  \n\n"
    expected = "@misc{fake,\n  title={Fake}\n}"
    assert clean_text(text) == expected, (
        "trailing spaces, the common indentation and the blank lines around"
        " should be removed"
    )
    assert clean_text(None) is None, "None should pass through"
