"""Storing the cards (cards/*.yaml, the docstring hash), and what the commands share.

Every script that touches a card goes through here, so a card is formatted the
same way no matter which script wrote it last. generate_cards.py and
compute_stats.py also share the dataset choice and the closing to-do list.

A card's docstring_hash is the SHA-256 of the loader docstring that produced
its summary. generate_cards.py reruns the LLM only when the current docstring
hashes differently, so unchanged datasets never cost model time and never get
a slightly different summary.
"""

import hashlib
import os

import yaml

from stats import PARTS


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


# --- docstring hash -----------------------------------------------------------


def docstring_hash(text):
    """Hex SHA-256 of a string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --- shared by the commands ---------------------------------------------------

DEFAULT_DATASETS_DIR = os.path.join(
    os.path.expanduser("~"), "mir_datasets"
)  # mirdata's default


def select_datasets(all_names, dataset=None, exclude=""):
    """The datasets to run: one (--dataset) or all, minus the comma-separated --exclude."""
    names = list(all_names)
    if dataset:
        if dataset not in names:
            raise SystemExit(f"Dataset '{dataset}' not found in mirdata.")
        names = [dataset]
    excluded = {n.strip() for n in exclude.split(",") if n.strip()}
    return [n for n in names if n not in excluded]


def print_to_do(results, command):
    """List the datasets whose parts need a local run, and those left incomplete or failing.

    results: {name: {"error"?, "audio"?, "annotations"?}}, each part with a
    "status" and "problems" (or "error"): a compute result or a card's stats
    field, which have the same shape. command: how to rerun one dataset
    locally, shown in the heading.
    """
    groups = {"needs_local": [], "incomplete": [], "error": []}
    for name, result in results.items():
        if not result:
            continue
        if result.get("error"):
            groups["error"].append((name, "", result["error"]))
        for part in PARTS:
            stats = result.get(part)
            if stats and stats.get("status") in groups:
                why = (
                    stats.get("problems") or [stats.get("error") or "see its errors"]
                )[0]
                groups[stats["status"]].append((name, part, why))
    titles = {
        "needs_local": f"Run these locally ({command}):",
        "incomplete": "Incomplete (some files could not be read; a local run would not help):",
        "error": "Failed:",
    }
    for status, rows in groups.items():
        if rows:
            print(f"\n{titles[status]}")
            for name, part, why in rows:
                print(f"  {name:28s} {part:12s} {why[:110]}")
