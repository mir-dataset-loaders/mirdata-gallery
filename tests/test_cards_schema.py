"""The contract every cards/*.yaml must satisfy.

SCHEMA — one entry per field, each a small dict of rules. This is the part
to edit when the card format changes. Every field listed is required and no
other keys are allowed in a card.

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

Two rules apply to every card and are not per-field:
 - `name` must equal the file name without .yaml
 - no string may have trailing whitespace at the end of a line
"""

import re

NoneType = type(None)

# =============================================================================
# 1. SCHEMA
# =============================================================================

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

AVAILABILITY = {
    "free": "✅ Freely downloadable",
    "request": "🔑 Available upon request",
    "diy": "📺 Do-it-yourself download",
    "features_only": "🧮 Features only",
    "unavailable": "❌ Not available",
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
        "choices": list(AVAILABILITY),
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
}


# =============================================================================
# 2. VALIDATION
# =============================================================================


def validate_card(card, filename=None):
    """Return a list of problems with `card` (a loaded YAML dict). Empty = valid.

    `filename` is the card's file name (e.g. "beatles.yaml"); when given, the
    `name` field must match it.
    """
    if not isinstance(card, dict):
        return [f"card is not a mapping (got {type(card).__name__})"]

    errors = []

    missing = [k for k in SCHEMA if k not in card]
    extra = [k for k in card if k not in SCHEMA]
    if missing:
        errors.append(f"missing keys: {', '.join(missing)}")
    if extra:
        errors.append(f"unknown keys: {', '.join(extra)}")

    for key, rules in SCHEMA.items():
        if key in card:
            errors.extend(f"{key}: {msg}" for msg in _check_field(card[key], rules))

    if filename is not None and isinstance(card.get("name"), str):
        expected = filename.removesuffix(".yaml")
        if card["name"] != expected:
            errors.append(
                f"name: '{card['name']}' does not match file name '{filename}'"
            )

    for key, value in card.items():
        if isinstance(value, str) and any(
            line != line.rstrip() for line in value.splitlines()
        ):
            errors.append(f"{key}: trailing whitespace at end of line")

    return errors


def _check_field(value, rules):
    """Apply the rules of one field to its value; yield messages for failures."""
    allowed = rules["type"]
    if not isinstance(value, allowed):
        yield f"expected {_type_names(allowed)}, got {type(value).__name__}"
        return  # the remaining rules assume the right type
    if value is None:
        return  # null is allowed by `type`; nothing else to check

    if isinstance(value, str):
        if "min_length" in rules and len(value.strip()) < rules["min_length"]:
            yield f"shorter than {rules['min_length']} character(s) (or only whitespace)"
        if rules.get("single_line") and "\n" in value.strip():
            yield "must be a single line"
        if "starts_with" in rules and not value.lstrip().startswith(
            rules["starts_with"]
        ):
            yield f"must start with {rules['starts_with']!r}"
        if "pattern" in rules and not re.fullmatch(rules["pattern"], value):
            yield f"does not match pattern {rules['pattern']!r}"

    if isinstance(value, list):
        if "items" in rules:
            bad = [v for v in value if not isinstance(v, rules["items"])]
            if bad:
                yield f"every element must be {_type_names(rules['items'])}; got {bad}"
        if "min_items" in rules and len(value) < rules["min_items"]:
            yield f"needs at least {rules['min_items']} element(s), got {len(value)}"
        if rules.get("unique") and len(value) != len(set(map(str, value))):
            yield "contains duplicates"
        if rules.get("sorted") and value != sorted(value, key=str):
            yield f"not sorted (expected {sorted(value, key=str)})"

    if "choices" in rules:
        values = value if isinstance(value, list) else [value]
        unknown = [v for v in values if v not in rules["choices"]]
        if unknown:
            yield f"unknown value(s) {unknown}; allowed: {rules['choices']}"


def _type_names(allowed):
    types = allowed if isinstance(allowed, tuple) else (allowed,)
    return " or ".join("null" if t is NoneType else t.__name__ for t in types)


# =============================================================================
# 3. TESTS
# =============================================================================

import os

import pytest
import yaml

CARDS_DIR = os.path.join(os.path.dirname(__file__), "..", "cards")
CARD_FILES = sorted(f for f in os.listdir(CARDS_DIR) if f.endswith(".yaml"))


@pytest.mark.parametrize("filename", CARD_FILES, ids=lambda f: f.removesuffix(".yaml"))
def test_card_matches_schema(filename):
    with open(os.path.join(CARDS_DIR, filename), encoding="utf-8") as f:
        card = yaml.safe_load(f)

    errors = validate_card(card, filename)
    assert not errors, f"cards/{filename}:\n" + "\n".join(f"  - {e}" for e in errors)


def test_validator_reports_every_problem():
    """Guard for the validator itself: wrong types, extra and missing keys."""
    errors = validate_card({"name": 5, "annotations": "BeatData", "bogus": 1}, "x.yaml")
    assert any(e.startswith("missing keys") for e in errors)
    assert any(e.startswith("unknown keys") for e in errors)
    assert "name: expected str, got int" in errors
    assert "annotations: expected list, got str" in errors
