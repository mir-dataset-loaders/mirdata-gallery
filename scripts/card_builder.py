"""What goes into a card: one function per field, and build_card to put them together.

Each field function takes an initialized mirdata Dataset (from ``mirdata.initialize``)
or the card's stats, and returns the value to store in the card. Function names
match the card fields on purpose, so build_card reads like the card itself.
clean_text tidies mirdata's text (license, bibtex, the loader docstring) for the YAML.
"""

import textwrap

# The MIR tasks each annotation type supports, by the names MIR papers use.
# EventData (and baf's EventDataExtended) is too generic to name one.
TASKS = {
    "BeatData": ["Beat Tracking"],
    "ChordData": ["Chord Recognition"],
    "F0Data": ["Melody Extraction"],
    "KeyData": ["Key Estimation"],
    "LyricData": ["Lyrics Transcription", "Lyrics-to-Audio Alignment"],
    "MultiF0Data": ["Multi-pitch Estimation"],
    "NoteData": ["Music Transcription"],
    "SectionData": ["Music Structure Analysis"],
    "TempoData": ["Tempo Estimation"],
    "Instrument": ["Instrument Recognition"],
}
# A loader with a MultiTrack class has the stems to separate
MULTITRACK_TASK = "Source Separation"


def build_card(ds, stats=None):
    """The card dict for one initialized dataset; keys in card order.

    stats is the card's stats field, from generate_cards.update_stats() (new,
    kept from the old card, or None); annotations and tasks come from it.
    summary, summary_hash, availability and availability_hash are left None:
    they come from the LLM, so generate_cards fills them in afterwards.
    """
    return {
        "name": ds.name,
        "summary": None,
        "annotations": annotations(stats),
        "tasks": tasks(ds, stats),
        "availability": None,
        "stats": stats,
        "summary_hash": None,
        "availability_hash": None,
        "bibtex": bibtex(ds),
        "license": license(ds),
    }


def license(ds):
    return clean_text(getattr(ds, "_license_info", "Not specified"))


def bibtex(ds):
    return clean_text(getattr(ds, "bibtex", None))


def annotations(stats):
    """Sorted list of the annotation types the stats read; empty without stats entries."""
    entries = ((stats or {}).get("annotations") or {}).get("annotations") or {}
    return sorted({entry["type"] for entry in entries.values()})


def tasks(ds, stats):
    """Sorted list of MIR tasks: those of the card's annotation types, plus Source Separation for a multitrack loader."""
    found = {task for t in annotations(stats) for task in TASKS.get(t, [])}
    if getattr(ds, "_multitrack_class", None):
        found.add(MULTITRACK_TASK)
    return sorted(found)


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
