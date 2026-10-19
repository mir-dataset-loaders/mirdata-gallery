"""Storing the cards: cards/*.yaml, the docstring hashes, and text tidying.

Every script that touches a card goes through here, so a card is formatted the
same way no matter which script wrote it last.

cards/docstring_hashes.json maps dataset name -> SHA-256 of the loader
docstring that produced the card's summary. generate_cards.py reruns the LLM
only when the current docstring hashes differently, so unchanged datasets
never cost model time and never get a slightly different summary.
"""

import hashlib
import json
import os
import textwrap

import yaml


def card_path(cards_dir, name):
    return os.path.join(cards_dir, f"{name}.yaml")


def read_card(path):
    """The card as a dict, or None if the file doesn't exist."""
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def write_card(path, card):
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(card, f, Dumper=_CardDumper, sort_keys=False, allow_unicode=True)


# --- YAML style ---------------------------------------------------------------


def _str_presenter(dumper, data):
    """Multi-line strings use the `|` block style so they stay readable."""
    style = "|" if "\n" in data else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


def _list_presenter(dumper, data):
    """Lists of numbers (histogram edges and counts) go on one line: [1, 2, 22, 26]."""
    flow = bool(data) and all(
        isinstance(v, (int, float)) and not isinstance(v, bool) for v in data
    )
    return dumper.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=flow)


class _CardDumper(yaml.SafeDumper):
    """Our dump settings, kept off the global yaml.Dumper."""


_CardDumper.add_representer(str, _str_presenter)
_CardDumper.add_representer(list, _list_presenter)


# --- docstring hashes ---------------------------------------------------------

HASHES_FILENAME = "docstring_hashes.json"


def docstring_hash(text):
    """Hex SHA-256 of a string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def hashes_path(cards_dir):
    return os.path.join(cards_dir, HASHES_FILENAME)


def read_hashes(cards_dir):
    """The name -> hash map, or {} if the file doesn't exist."""
    p = hashes_path(cards_dir)
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def write_hashes(cards_dir, mapping):
    """Save the map with sorted keys so the git diff stays readable."""
    with open(hashes_path(cards_dir), "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2, sort_keys=True)
        f.write("\n")


# --- text ---------------------------------------------------------------------


def clean_text(text):
    """Tidy a multi-line string from mirdata so it stores cleanly in YAML.

    Drops trailing spaces on every line (PyYAML refuses the readable `|`
    block style otherwise), removes common indentation, and strips blank
    lines around the text. Non-strings (None) pass through unchanged.
    """
    if not isinstance(text, str):
        return text
    lines = [line.rstrip() for line in text.splitlines()]
    return textwrap.dedent("\n".join(lines)).strip()
