"""What every card in cards/ must look like: the format the gallery page is built from.

check_card() and check_stats() hold the rules, one assert each, and run on every
committed card. Edit this file when the format changes.
"""

import os
import re

import pytest

import card_utils

CARDS_DIR = os.path.join(os.path.dirname(__file__), "..", "cards")
CARD_FILES = sorted(f for f in os.listdir(CARDS_DIR) if f.endswith(".yaml"))

FIELDS = [
    "name",
    "summary",
    "annotations",
    "stats",
    "docstring_hash",
    "bibtex",
    "license",
]
# The card's annotations field: mirdata's annotation types plus a few labels
# that are not classes. Each one has a colour in docs/_static/css/custom.css.
CARD_TYPES = {
    "BeatData",
    "ChordData",
    "EventData",
    "EventDataExtended",
    "F0Data",
    "Genre",
    "Instrument",
    "KeyData",
    "LyricData",
    "MultiF0Data",
    "NoteData",
    "SectionData",
    "TempoData",
}
STATUSES = {"ok", "incomplete", "needs_local", "error"}
MODES = {"remote", "local"}
NAME = re.compile(r"[a-z0-9_]+")
SHA256 = re.compile(r"[0-9a-f]{64}")
HISTOGRAM_KEYS = {"unit", "edges", "counts"}
CRASHED_PART = {"status", "error"}
DATASET_ERROR = {"computed", "error"}
STATS_KEYS = {"computed", "audio", "annotations"}
AUDIO_FIELDS = {
    "status",
    "problems",
    "n_tracks",
    "n_audio_files",
    "total_seconds",
    "sample_rate",
    "duration_histogram",
}
ANNOTATION_FIELDS = {
    "status",
    "problems",
    "n_tracks",
    "n_tracks_loaded",
    "tracks_with",
    "annotations",
    "skipped",
    "n_missing_files",
    "n_track_errors",
    "annotation_errors",
}
# The fields of an annotation entry, by type, besides type, n_tracks,
# n_annotations and the optional parts.
HISTOGRAM, COUNTS = "histogram", "counts"
ENTRY_FIELDS = {
    "BeatData": {"tempo_from_beats": HISTOGRAM, "meter": COUNTS},
    "ChordData": {"labels": COUNTS, "qualities": COUNTS},
    "EventData": {"events": COUNTS},
    "F0Data": {"frequencies": HISTOGRAM},
    "KeyData": {"keys": COUNTS, "modes": COUNTS},
    "LyricData": {"lyric_unit": COUNTS, "lyrics_per_track": HISTOGRAM},
    "MultiF0Data": {"frequencies": HISTOGRAM, "polyphony": COUNTS},
    "NoteData": {"pitches": HISTOGRAM},
    "SectionData": {"labels": COUNTS, "section_interval_seconds": HISTOGRAM},
    "TempoData": {"tempo": HISTOGRAM},
}


def is_count(value):
    """A whole number >= 0 (and not True or False, which are ints in Python)."""
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def check_text(text, field):
    assert isinstance(text, str) and text.strip(), f"{field} should be non-empty text"
    trailing = [line for line in text.splitlines() if line != line.rstrip()]
    assert not trailing, f"{field}: no line should end in spaces (breaks the | style)"


def check_counts(value, where):
    assert isinstance(value, dict), f"{where} should be {{label: count}}"
    whole = all(is_count(n) for n in value.values())
    assert whole, f"{where} should count whole numbers >= 0"


def check_histogram(value, where):
    if value is None:
        return  # no values to bin, e.g. no track with two beats
    assert set(value) == HISTOGRAM_KEYS, f"{where} should be {{unit, edges, counts}}"
    edges, counts = value["edges"], value["counts"]
    assert isinstance(value["unit"], str), f"{where} unit should be text"
    one_more = len(edges) == len(counts) + 1
    assert one_more, f"{where} should have one more edge than counts"
    increasing = all(a < b for a, b in zip(edges, edges[1:]))
    assert increasing, f"{where} edges should increase"
    whole = all(is_count(n) for n in counts)
    assert whole, f"{where} counts should be whole numbers >= 0"


def check_entry(prop, entry):
    where = f"annotations.{prop}"
    ann_type = entry.get("type")
    assert ann_type in ENTRY_FIELDS, f"{where} type should be a mirdata annotation type"
    fields = ENTRY_FIELDS[ann_type]
    expected = {"type", "n_tracks", "n_annotations", *fields}
    has_fields = set(entry) - {"parts"} == expected
    assert has_fields, f"{where} should have the fields of {ann_type}"
    assert is_count(entry["n_tracks"]), f"{where} n_tracks should be a count"
    enough = entry["n_annotations"] >= entry["n_tracks"]
    assert enough, f"{where} should have at least one annotation per track"
    if "parts" in entry:
        check_counts(entry["parts"], f"{where}.parts")
    for field, kind in fields.items():
        check = check_histogram if kind == HISTOGRAM else check_counts
        check(entry[field], f"{where}.{field}")


def check_part(part, value, fields):
    assert value.get("status") in STATUSES, f"{part} status should be one of {STATUSES}"
    if value["status"] == "error":
        only_error = set(value) == CRASHED_PART
        assert only_error, f"a crashed {part} should hold only status and error"
        return False
    assert set(value) == fields, f"{part} should have exactly its fields"
    problems = value["problems"]
    assert isinstance(problems, list), f"{part} problems should be a list"
    needs_local = value["status"] == "needs_local"
    matches = needs_local == bool(problems)
    assert matches, f"{part} should be needs_local exactly when it has problems"
    return True


def check_card(card, name):
    """The rules for the card's fields; check_stats() has those of its stats field."""
    assert list(card) == FIELDS, f"a card should have exactly {FIELDS}, in this order"
    assert card["name"] == name, "name should be the file name without .yaml"
    assert NAME.fullmatch(name), "name should be lowercase letters, digits and _"
    check_text(card["license"], "license")
    assert "\n" not in card["license"], "license should be one line"
    types = card["annotations"]
    assert types, "annotations should list at least one type"
    unknown = set(types) - CARD_TYPES
    assert not unknown, f"annotations should only use known types, not {unknown}"
    in_order = types == sorted(set(types))
    assert in_order, "annotations should be sorted, without duplicates"
    check_text(card["bibtex"], "bibtex")
    assert card["bibtex"].lstrip().startswith("@"), "bibtex should be a BibTeX entry"
    check_text(card["summary"], "summary")
    hashed = str(card["docstring_hash"])
    assert SHA256.fullmatch(hashed), "docstring_hash should be a SHA-256"
    assert isinstance(card["stats"], dict), "stats should be computed"


def check_stats(stats):
    computed = stats.get("computed") or {}
    assert computed.get("mode") in MODES, f"computed.mode should be one of {MODES}"
    index = computed.get("index")
    assert isinstance(index, str), "computed.index should be the index checksum"
    if "error" in stats:
        only_error = set(stats) == DATASET_ERROR
        assert only_error, "a dataset error should hold only computed and the error"
        return
    assert set(stats) == STATS_KEYS, "stats should hold computed, audio and annotations"

    audio = stats["audio"]
    if check_part("audio", audio, AUDIO_FIELDS):
        assert is_count(audio["n_tracks"]), "audio n_tracks should be a count"
        assert is_count(audio["n_audio_files"]), "audio n_audio_files should be a count"
        seconds = audio["total_seconds"]
        positive = isinstance(seconds, (int, float)) and seconds >= 0
        assert positive, "total_seconds should be a number >= 0"
        assert is_count(audio["sample_rate"]), "sample_rate should be a whole number"
        check_histogram(audio["duration_histogram"], "duration_histogram")

    ann = stats["annotations"]
    if check_part("annotations", ann, ANNOTATION_FIELDS):
        for key in ("n_tracks", "n_tracks_loaded", "n_missing_files", "n_track_errors"):
            assert is_count(ann[key]), f"annotations {key} should be a count"
        loaded = ann["n_tracks_loaded"] <= ann["n_tracks"]
        assert loaded, "no more tracks should load than there are"
        check_counts(ann["tracks_with"], "tracks_with")
        check_counts(ann["annotation_errors"], "annotation_errors")
        assert isinstance(ann["skipped"], dict), "skipped should be {property: why}"
        for prop, entry in ann["annotations"].items():
            check_entry(prop, entry)


@pytest.mark.parametrize("filename", CARD_FILES)
def test_card(filename):
    card = card_utils.read_card(os.path.join(CARDS_DIR, filename))
    check_card(card, filename.removesuffix(".yaml"))


@pytest.mark.parametrize("filename", CARD_FILES)
def test_card_stats(filename):
    card = card_utils.read_card(os.path.join(CARDS_DIR, filename))
    check_stats(card["stats"])
