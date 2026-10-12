"""Remember which docstring each summary was made from.

cards/docstring_hashes.json maps dataset name -> SHA-256 of the loader
docstring that produced the card's summary. generate_cards.py reruns the LLM
only when the current docstring hashes differently, so unchanged datasets
never cost model time and never get a slightly different summary.
"""

import hashlib
import json
import os

FILENAME = "docstring_hashes.json"


def of(text):
    """Hex SHA-256 of a string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def path(cards_dir):
    return os.path.join(cards_dir, FILENAME)


def read(cards_dir):
    """The name -> hash map, or {} if the file doesn't exist."""
    p = path(cards_dir)
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def write(cards_dir, mapping):
    """Save the map with sorted keys so the git diff stays readable."""
    with open(path(cards_dir), "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2, sort_keys=True)
        f.write("\n")
