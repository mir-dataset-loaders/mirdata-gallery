"""stats/to_card.py: a compute() result turned into a card's stats field, and which stats to keep.

The results here are written by hand, so what is kept, dropped and converted
shows in the test itself.
"""

import pytest

from stats.to_card import choose, is_current, result_to_card_stats

AUDIO = {"status": "ok", "problems": [], "n_tracks": 3, "n_audio_files": 3}
TEMPO = {"unit": "bpm", "edges": [0, 100, 200], "counts": [1, 1]}
PITCHES = {"unit": "midi", "edges": [59.5, 60.5], "counts": [4]}
ANNOTATIONS = {  # a remote run where track3 failed and one beats file was corrupt
    "n_tracks": 3,
    "n_tracks_loaded": 2,
    "tracks_with": {"BeatData": 1, "MultiF0Data": 2},
    "annotations": {
        "beats": {
            "type": "BeatData",
            "n_tracks": 1,
            "n_annotations": 1,
            "meter": {"3": 1},  # as it comes back from JSON: keys are text
            "tempo_from_beats": TEMPO,
        },
        "notes": {
            "type": "MultiF0Data",
            "n_tracks": 2,
            "n_annotations": 2,
            "frequencies": PITCHES,
            "polyphony": {"1": 3, "2": 1},
        },
    },
    "skipped": {"title": "not a mirdata ChordData object (got str)"},
    "errors": {"track3": "ValueError: cannot build track3"},
    "annotation_errors": {
        "beats": {"n_tracks": 1, "examples": {"track2": "ValueError: bad line"}}
    },
    "status": "incomplete",
    "problems": [],
    "sources": ["  annotations            annotations.zip: 0.00 GB  5 matched"],
    "missing_files": {"annotations/beats/track2.txt": "ValueError: CRC mismatch"},
}
RESULT = {"name": "fake_dataset", "audio": AUDIO, "annotations": ANNOTATIONS}


def card_stats(index, audio="ok", annotations="ok"):
    """A card's stats field computed from this index, with these part statuses."""
    return {
        "computed": {"mode": "remote", "index": index},
        "audio": {"status": audio},
        "annotations": {"status": annotations},
    }


# ------------------------------------------------------- result_to_card_stats


def test_result_to_card_stats():
    card = result_to_card_stats(RESULT, "remote", "abc123")
    assert set(card) == {
        "computed",
        "audio",
        "annotations",
    }, "the card stats should hold computed and both parts"
    computed = {"mode": "remote", "index": "abc123"}
    assert (
        card["computed"] == computed
    ), "computed should record the mode and the index checksum"
    assert card["audio"] == AUDIO, "audio should keep its status, problems and counts"

    ann = card["annotations"]
    kept = {
        "status",
        "problems",
        "n_tracks",
        "n_tracks_loaded",
        "tracks_with",
        "annotations",
        "skipped",
    }
    counts = {"n_missing_files", "n_track_errors", "annotation_errors"}
    assert (
        set(ann) == kept | counts
    ), "annotations should drop the log lines and the per-file details"
    for key in kept - {"annotations"}:
        assert ann[key] == ANNOTATIONS[key], f"{key} should be kept as it is"
    assert ann["n_missing_files"] == 1, "missing_files should become their number"
    assert ann["n_track_errors"] == 1, "track errors should become their number"
    per_property = {"beats": 1}
    assert (
        ann["annotation_errors"] == per_property
    ), "annotation errors should become tracks per property"

    beats, notes = ann["annotations"]["beats"], ann["annotations"]["notes"]
    meter = {3: 1}
    assert (
        beats["meter"] == meter
    ), "meter keys should be numbers again, even after a JSON round trip"
    assert notes["polyphony"] == {1: 3, 2: 1}, "polyphony keys should be numbers again"
    assert beats["tempo_from_beats"] == TEMPO, "histograms should be kept as they are"
    assert notes["frequencies"] == PITCHES, "histograms should be kept as they are"


def test_result_to_card_stats_errors():
    failed = {"name": "fake_dataset", "error": "ImportError: no module named x"}
    card = result_to_card_stats(failed, "remote", "abc123")
    expected = {
        "computed": {"mode": "remote", "index": "abc123"},
        "error": failed["error"],
    }
    assert (
        card == expected
    ), "a dataset that could not load should keep only computed and the error"

    crashed = {"status": "error", "error": "RuntimeError: loader bug"}
    card = result_to_card_stats({**RESULT, "annotations": crashed}, "local", "abc123")
    assert (
        card["annotations"] == crashed
    ), "a crashed part should keep only its status and error"
    assert card["audio"] == AUDIO, "the other part should be converted as usual"


def test_result_to_card_stats_parts():
    audio_only = {"name": "fake_dataset", "audio": AUDIO}
    card = result_to_card_stats(audio_only, "local", "abc123")
    parts = {"computed", "audio"}
    assert set(card) == parts, "only the parts in the result should be in the card"


def test_result_to_card_stats_mode():
    with pytest.raises(ValueError):
        result_to_card_stats(RESULT, "cloud", "abc123")


# ------------------------------------------------------ keeping or replacing


def test_is_current():
    stats = card_stats("abc123")
    assert is_current(stats, "abc123"), "stats from the same index should be current"
    assert not is_current(
        stats, "def456"
    ), "stats from another index should not be current"
    assert not is_current(None, "abc123"), "no stats should not be current"
    no_computed = {"audio": {"status": "ok"}}
    assert not is_current(
        no_computed, "abc123"
    ), "stats without a computed block should not be current"


def test_choose():
    new = card_stats("abc123", annotations="needs_local")
    assert (
        choose(None, new, "abc123") is new
    ), "with no old stats, the new ones should be kept"

    old = card_stats("def456", annotations="ok")
    assert (
        choose(old, new, "abc123") is new
    ), "stats from another index should be replaced, however complete"

    # e.g. a local run, before a remote one
    old = card_stats("abc123", annotations="ok")
    assert (
        choose(old, new, "abc123") is old
    ), "more complete stats from the same index should be kept"

    old = card_stats("abc123", annotations="needs_local")
    assert (
        choose(old, new, "abc123") is new
    ), "as complete new stats should replace the old ones"

    # error < needs_local < incomplete < ok, and the worst part decides
    order = ["error", "needs_local", "incomplete", "ok"]
    for worse, better in zip(order, order[1:]):
        old = card_stats("abc123", annotations=better)
        new = card_stats("abc123", annotations=worse)
        assert choose(old, new, "abc123") is old, f"{better} should rank above {worse}"
    old = card_stats("abc123", annotations="incomplete")
    new = card_stats("abc123", audio="error", annotations="ok")
    assert (
        choose(old, new, "abc123") is old
    ), "the worst part should decide: error ranks below incomplete"
    failed = {"computed": {"mode": "remote", "index": "abc123"}, "error": "ImportError"}
    new = card_stats("abc123", annotations="needs_local")
    assert choose(failed, new, "abc123") is new, "a dataset error should rank lowest"
