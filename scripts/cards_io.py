"""Read and write cards/*.yaml.

Every script that touches a card goes through here, so a card is formatted the
same way no matter which script wrote it last.
"""

import os

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
