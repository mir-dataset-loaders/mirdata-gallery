"""Check every cards/*.yaml against the schema in card_schema.py.

One test per card, so a failure names the card and lists every rule it breaks.
"""

import os
import re
from types import NoneType

import pytest
import yaml

from card_schema import (
    SCHEMA,
    STATS_ANNOTATION_COMMON,
    STATS_ANNOTATION_FIELDS,
    STATS_MODES,
    STATS_PARTS,
    STATS_STATUSES,
)

CARDS_DIR = os.path.join(os.path.dirname(__file__), "..", "cards")
CARD_FILES = sorted(f for f in os.listdir(CARDS_DIR) if f.endswith(".yaml"))


# =============================================================================
# Validation — applies the rule keywords documented in card_schema.py
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

    if rules.get("stats") and isinstance(value, dict):
        yield from _check_stats(value)


def _check_stats(stats):
    """The structure of the "stats" field; see STATS_* in card_schema.py."""
    extra = [k for k in stats if k not in ["computed", "error", *STATS_PARTS]]
    if extra:
        yield f"unknown keys: {', '.join(map(str, extra))}"

    computed = stats.get("computed")
    if not isinstance(computed, dict):
        yield "computed: missing (needs mode, index)"
    else:
        if computed.get("mode") not in STATS_MODES:
            yield f"computed.mode: must be one of {STATS_MODES}, got {computed.get('mode')!r}"
        if not isinstance(computed.get("index"), str) or not computed.get("index"):
            yield "computed.index: must be the index checksum (a string)"

    if "error" in stats:
        if not isinstance(stats["error"], str):
            yield "error: must be a string"
    elif not any(part in stats for part in STATS_PARTS):
        yield f"needs at least one of {STATS_PARTS} (or an error)"

    for part in STATS_PARTS:
        if part not in stats:
            continue
        value = stats[part]
        if not isinstance(value, dict):
            yield f"{part}: expected dict, got {type(value).__name__}"
            continue
        status = value.get("status")
        if status not in STATS_STATUSES:
            yield f"{part}.status: must be one of {STATS_STATUSES}, got {status!r}"
        if status == "error":
            if not isinstance(value.get("error"), str):
                yield f"{part}.error: an error part needs its message"
        elif not isinstance(value.get("problems"), list) or not all(
            isinstance(p, str) for p in value["problems"]
        ):
            yield f"{part}.problems: must be a list of strings"
        elif status == "needs_local" and not value["problems"]:
            yield f"{part}.problems: needs_local must say why"
        yield from _check_histograms(value, part)
        if part == "annotations":
            yield from _check_annotation_entries(value.get("annotations") or {})


def _check_annotation_entries(entries):
    """Each entry under stats.annotations.annotations: its type's fields, nothing else."""
    for prop, entry in entries.items():
        where = f"annotations.annotations.{prop}"
        if not isinstance(entry, dict):
            yield f"{where}: expected dict, got {type(entry).__name__}"
            continue
        fields = STATS_ANNOTATION_FIELDS.get(entry.get("type"))
        if fields is None:
            yield f"{where}.type: must be one of {sorted(STATS_ANNOTATION_FIELDS)}, got {entry.get('type')!r}"
            continue
        missing = [k for k in [*STATS_ANNOTATION_COMMON, *fields] if k not in entry]
        if missing:
            yield f"{where}: missing keys: {', '.join(missing)}"
        allowed = [*STATS_ANNOTATION_COMMON, "parts", *fields]
        extra = [k for k in entry if k not in allowed]
        if extra:
            yield f"{where}: unknown keys: {', '.join(map(str, extra))}"
        for key in ["n_tracks", "n_annotations"]:
            if key in entry and (not isinstance(entry[key], int) or entry[key] < 0):
                yield f"{where}.{key}: must be a non-negative integer"
        for key, kind in fields.items():
            value = entry.get(key)
            if key not in entry:
                continue
            if kind == "histogram" and value is not None and (
                not isinstance(value, dict) or set(value) != {"unit", "edges", "counts"}
            ):
                yield f"{where}.{key}: must be a histogram {{unit, edges, counts}} or null"
            if kind == "counts" and (
                not isinstance(value, dict)
                or not all(isinstance(c, int) and c >= 0 for c in value.values())
            ):
                yield f"{where}.{key}: must be {{label: count}} with non-negative integer counts"


def _check_histograms(value, where):
    """Every {unit, edges, counts} under value: one more edge than counts, rising edges."""
    if isinstance(value, dict):
        if set(value) == {"unit", "edges", "counts"}:
            edges, counts = value["edges"], value["counts"]
            if not isinstance(edges, list) or not isinstance(counts, list):
                yield f"{where}: edges and counts must be lists"
            elif len(edges) != len(counts) + 1:
                yield f"{where}: {len(edges)} edges for {len(counts)} counts (needs one more edge)"
            elif any(b <= a for a, b in zip(edges, edges[1:])):
                yield f"{where}: edges must rise"
            elif any(not isinstance(c, int) or c < 0 for c in counts):
                yield f"{where}: counts must be non-negative integers"
            return
        for key, item in value.items():
            yield from _check_histograms(item, f"{where}.{key}")


def _type_names(allowed):
    types = allowed if isinstance(allowed, tuple) else (allowed,)
    return " or ".join("null" if t is NoneType else t.__name__ for t in types)


# =============================================================================
# Tests
# =============================================================================


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


# =============================================================================
# The stats field
# =============================================================================


def _stats_errors(stats):
    return list(_check_field(stats, SCHEMA["stats"]))


def BEATS(stats):
    """The beats entry of a stats dict, for the cases below."""
    return stats["annotations"]["annotations"]["beats"]


VALID_STATS = {
    "computed": {"mode": "remote", "index": "cb3998bcae39d9c1"},
    "audio": {"status": "ok", "problems": [], "n_tracks": 3, "n_audio_files": 3},
    "annotations": {
        "status": "needs_local",
        "problems": ["no remotes: the annotations have to be downloaded manually"],
        "annotations": {
            "beats": {
                "type": "BeatData",
                "n_tracks": 3,
                "n_annotations": 3,
                "meter": {4: 3},
                "tempo_from_beats": {"unit": "bpm", "edges": [60, 80], "counts": [3]},
            }
        },
    },
}


def test_valid_stats_and_null_pass():
    assert _stats_errors(VALID_STATS) == []
    assert _stats_errors(None) == []
    assert _stats_errors({"computed": VALID_STATS["computed"], "error": "ImportError: x"}) == []
    error_part = {"computed": VALID_STATS["computed"], "audio": {"status": "error", "error": "RuntimeError: x"}}
    assert _stats_errors(error_part) == []


def test_annotation_entries_may_have_parts_and_null_histograms():
    import copy

    stats = copy.deepcopy(VALID_STATS)
    BEATS(stats).update(parts={"annotator_1": 3}, tempo_from_beats=None)
    assert _stats_errors(stats) == []


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda s: s.pop("computed"), "computed: missing"),
        (lambda s: s["computed"].update(mode="cloud"), "computed.mode"),
        (lambda s: s["computed"].update(index=""), "computed.index"),
        (lambda s: s.update(extra=1), "unknown keys: extra"),
        (lambda s: s["audio"].update(status="fine"), "audio.status"),
        (lambda s: s["audio"].pop("problems"), "audio.problems: must be a list"),
        (lambda s: s["annotations"].update(problems=[]), "needs_local must say why"),
        (lambda s: BEATS(s)["tempo_from_beats"].update(counts=[1, 2]), "2 edges for 2 counts"),
        (lambda s: BEATS(s)["tempo_from_beats"].update(edges=[80, 60]), "edges must rise"),
        (lambda s: BEATS(s)["tempo_from_beats"].update(counts=[-3]), "non-negative integers"),
        (lambda s: (s.pop("audio"), s.pop("annotations")), "needs at least one of"),
        (lambda s: BEATS(s).update(type="Beats"), "beats.type: must be one of"),
        (lambda s: BEATS(s).pop("meter"), "beats: missing keys: meter"),
        (lambda s: BEATS(s).pop("n_tracks"), "beats: missing keys: n_tracks"),
        (lambda s: BEATS(s).update(beats_per_annotation={}), "beats: unknown keys: beats_per_annotation"),
        (lambda s: BEATS(s).update(n_tracks=-1), "beats.n_tracks: must be a non-negative integer"),
        (lambda s: BEATS(s).update(tempo_from_beats=[60, 80]), "beats.tempo_from_beats: must be a histogram"),
        (lambda s: BEATS(s).update(meter={4: "three"}), "beats.meter: must be {label: count}"),
    ],
)
def test_invalid_stats_are_reported(change, message):
    import copy

    stats = copy.deepcopy(VALID_STATS)
    change(stats)
    errors = _stats_errors(stats)
    assert any(message in e for e in errors), errors


def test_real_stats_from_card_py_pass_the_schema():
    """The stats field to_card.py writes (here for a small fake result) is valid as is."""
    from stats.to_card import result_to_card_stats
    from test_to_card import ANNOTATIONS, AUDIO

    stats = result_to_card_stats({"name": "fake", "audio": AUDIO, "annotations": ANNOTATIONS}, "local", "abc")
    assert _stats_errors(stats) == []
