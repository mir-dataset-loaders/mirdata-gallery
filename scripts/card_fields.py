"""One function per card field.

Each function takes an initialized mirdata Dataset (from ``mirdata.initialize``)
and returns the value to store in the card. Function names match the card
fields on purpose, so ``generate_cards.py`` reads like the card itself.
"""

import importlib
import typing

import mirdata
from mirdata.annotations import Annotation

# FIXME: NEEDS FIX

# For track properties without a usable return type hint: if the property
# name contains the keyword, it counts as that annotation type. Substring
# match, first keyword in this order wins.
FALLBACK_MAP = {
    "beat": "BeatData",
    "chord": "ChordData",
    "key": "KeyData",
    "tempo": "TempoData",
    "section": "SectionData",
    "segment": "SectionData",
    "pitch": "F0Data",
    "f0": "F0Data",
    "melody": "F0Data",
    "note": "NoteData",
    "midi": "NoteData",
    "lyric": "LyricData",
    "phoneme": "LyricData",
    "syllable": "LyricData",
    "phrase": "LyricData",
    "tonic": "KeyData",
    "event": "EventData",
    "instrument": "Instrument",
}


def license(ds):
    value = getattr(ds, "_license_info", "Not specified")
    return value.strip() if isinstance(value, str) else value


def remotes(ds):
    return list(ds.remotes.keys()) if ds.remotes else []


def download_info(ds):
    return getattr(ds, "_download_info", None)


def bibtex(ds):
    return getattr(ds, "bibtex", None)


def docstring(ds):
    return importlib.import_module(f"mirdata.datasets.{ds.name}").__doc__


def annotations(ds):
    """Sorted list of annotation types the dataset's Track class exposes."""
    found = set()
    track_class = getattr(ds, "_track_class", None)
    if track_class:
        for attr in dir(track_class):
            if attr.startswith("_"):
                continue
            item = getattr(track_class, attr, None)
            if isinstance(item, (property, mirdata.core.cached_property)):
                ann_cls = _annotation_class_name(attr, item)
                if ann_cls:
                    found.add(ann_cls)

    # Dedicated genre datasets (gtzan_genre, acousticbrainz_genre, ...)
    if ds.name.endswith("_genre"):
        found.add("Genre")

    return sorted(found)


def _annotation_class_name(attr_name, item):
    """Annotation class name a property returns, or None if it isn't one."""
    # @property stores the getter as .fget, @cached_property as .func
    func = getattr(item, "func", None) or getattr(item, "fget", None)
    if not func:
        return None

    # 1. Return type hint, e.g. -> Optional[BeatData]
    ret = getattr(func, "__annotations__", {}).get("return")
    if ret:
        for arg in typing.get_args(ret):  # unwrap Optional[...] / Union[...]
            if arg is not type(None):
                ret = arg
                break
        if (
            isinstance(ret, type)
            and issubclass(ret, Annotation)
            and ret is not Annotation
        ):
            return ret.__name__

    # 2. Keyword in the property name
    attr_lower = attr_name.lower()
    for keyword, class_name in FALLBACK_MAP.items():
        if keyword in attr_lower:
            return class_name
    return None
