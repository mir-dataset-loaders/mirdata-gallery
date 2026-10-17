"""What every cards/*.yaml must look like.

This is the file to edit when the card format changes. The rules are enforced
by tests/test_cards_schema.py (run `pytest`).

SCHEMA has one entry per field, each a small dict of rules. Every field listed
is required, and a card may not contain any other keys.

Rule keywords:
 type         Python type, or a tuple of types. NoneType allows null.
 min_length   str: minimum length after stripping whitespace
 single_line  str: no line breaks allowed
 starts_with  str: must start with this (leading whitespace ignored)
 pattern      str: must fully match this regex
 items        list: type every element must have
 min_items    list: minimum number of elements
 unique       list: no duplicate elements
 sorted       list: elements must be in sorted order
 choices      the value (str) or every element (list) must be one of these
 stats        dict: the structure of the "stats" field (see STATS_* below):
              a "computed" block, parts with a valid status, every
              histogram {unit, edges, counts} well formed, and the fields
              of each annotation type (STATS_ANNOTATION_FIELDS)

Two rules apply to every card and are not per-field:
 - `name` must equal the file name without .yaml
 - no string may have trailing whitespace at the end of a line
"""

from types import NoneType

# Closed vocabulary for `annotations`. Mostly mirdata.annotations class names,
# plus a few classification labels (Instrument, Genre) that are not classes.
# Adding a value here also means adding a colour for it in
# docs/_static/css/custom.css.
ANNOTATION_TYPES = [
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
]

# Closed vocabulary for `audio`: how the audio can be obtained. Cards store the
# label itself and the gallery shows it as-is.
AUDIO_AVAILABILITY = [
    "✅ Freely downloadable",
    "🔑 Available upon request",
    "📺 Do-it-yourself download",
    "🧮 Features only",
    "❌ Not available",
]

# The "stats" field (written by scripts/generate_cards.py, see scripts/stats/card.py).
STATS_PARTS = ["audio", "annotations"]
STATS_STATUSES = ["ok", "incomplete", "needs_local", "error"]
STATS_MODES = ["remote", "local"]

# What each entry under stats.annotations.annotations holds (one entry per
# track property, see scripts/stats/annotation_types.py). Every entry has
# STATS_ANNOTATION_COMMON, plus "parts" ({key: count}) when a track holds
# several annotations (dict keys or annotators), plus the fields of its type.
# Field kinds:
#   histogram  {unit, edges, counts}, or null when there were no values
#   counts     {label: count}, the 10 most common, the rest under "(other)";
#              beats_per_bar has every meter, keyed by number
STATS_ANNOTATION_COMMON = ["type", "n_tracks", "n_annotations"]
STATS_ANNOTATION_FIELDS = {
    "BeatData": {"tempo": "histogram", "beats_per_bar": "counts"},
    "ChordData": {"labels": "counts", "qualities": "counts"},
    "EventData": {"labels": "counts"},
    "F0Data": {"f0_median_per_annotation": "histogram", "voiced_fraction": "histogram"},
    "KeyData": {"keys": "counts", "modes": "counts"},
    "LyricData": {},
    "MultiF0Data": {"max_polyphony": "histogram"},
    "NoteData": {"pitch": "histogram"},
    "SectionData": {"labels": "counts", "section_seconds": "histogram"},
    "TempoData": {"tempo": "histogram"},
}

SCHEMA = {
    "name": {
        "type": str,
        "pattern": r"[a-z0-9_]+",
    },
    "license": {
        "type": str,
        "min_length": 1,
        "single_line": True,
    },
    "audio": {
        "type": str,
        "choices": AUDIO_AVAILABILITY,
    },
    "annotations": {
        "type": list,
        "items": str,
        "min_items": 1,
        "unique": True,
        "sorted": True,
        "choices": ANNOTATION_TYPES,
    },
    "bibtex": {
        "type": str,
        "min_length": 1,
        "starts_with": "@",
    },
    # LLM summary shown as "About this dataset"
    "summary": {
        "type": (str, NoneType),
        "min_length": 1,
    },
    # Audio and annotation statistics; null until computed
    "stats": {
        "type": (dict, NoneType),
        "stats": True,
    },
}
