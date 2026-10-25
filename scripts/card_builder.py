"""What goes into a card: one function per field, and build_card to put them together.

Each field function takes an initialized mirdata Dataset (from ``mirdata.initialize``)
and returns the value to store in the card. Function names match the card
fields on purpose, so build_card reads like the card itself. clean_text tidies
mirdata's text (license, bibtex, the loader docstring) for the YAML.
"""

import textwrap
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


def build_card(ds, summary=None, docstring_hash=None, stats=None):
    """The card dict for one initialized dataset; keys in card order.

    summary, docstring_hash and stats are the card's summary, docstring_hash
    and stats fields, from generate_cards.update_summary() and update_stats()
    (new, kept from the old card, or None).
    """
    return {
        "name": ds.name,
        "license": license(ds),
        "annotations": annotations(ds),
        "bibtex": bibtex(ds),
        "summary": summary,
        "docstring_hash": docstring_hash,
        "stats": stats,
    }


def license(ds):
    return clean_text(getattr(ds, "_license_info", "Not specified"))


def bibtex(ds):
    return clean_text(getattr(ds, "bibtex", None))


def annotations(ds):
    """Sorted list of annotation types the dataset's Track class exposes."""
    found = set(annotation_properties(ds).values())
    # Dedicated genre datasets (gtzan_genre, acousticbrainz_genre, ...)
    if ds.name.endswith("_genre"):
        found.add("Genre")
    return sorted(found)


def annotation_properties(ds, guess=True):
    """{property name: annotation type} for every annotation property of the dataset's Track class.

    The card's annotations field lists the types; the stats read the
    properties of the official mirdata types. guess=False keeps only the
    properties whose return hint names the type (none guessed from FALLBACK_MAP).
    """
    found = {}
    track_class = getattr(ds, "_track_class", None)
    for attr in dir(track_class):
        if attr.startswith("_"):
            continue
        item = getattr(track_class, attr, None)
        if isinstance(item, (property, mirdata.core.cached_property)):
            ann_cls = _annotation_class_name(attr, item, guess)
            if ann_cls:
                found[attr] = ann_cls
    return found


def _annotation_class_name(attr_name, item, guess=True):
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
    if not guess:
        return None

    # 2. Keyword in the property name
    attr_lower = attr_name.lower()
    for keyword, class_name in FALLBACK_MAP.items():
        if keyword in attr_lower:
            return class_name
    return None


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
