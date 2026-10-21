"""Sphinx extension: render the mirdata dataset gallery straight from the cards.

Usage in an .rst file::

    .. dataset-gallery:: ../cards

The argument is the directory holding one YAML card per dataset, relative to
the current document. Each card becomes a section, the dataset's panel: its
title, an overview (the summary), an "At a glance" box, the statistics (the
plots' data, which charts.js draws as SVG bar charts), and the BibTeX
citation. gallery.js arranges the sections into the filterable gallery,
custom.css styles them.

Every card is registered as a dependency of the page, and the directory is
snapshotted, so editing, adding or removing a card makes Sphinx re-read the
page on the next incremental build without needing ``-E``.
"""

import html
import json
import os
import textwrap

import card_schema
import yaml
from card_schema import STATS_ANNOTATION_FIELDS
from docutils import nodes
from docutils.statemachine import StringList, string2lines
from sphinx.util import logging
from sphinx.util.docutils import SphinxDirective
from sphinx.util.nodes import nested_parse_with_titles

logger = logging.getLogger(__name__)

MAX_PARTS = 6  # part names written in a "Try it with mirdata" comment; the rest as "…"

# --- Card rendering ----------------------------------------------------------


def render_card(data, fallback_name):
    """Return the RST for one dataset card.

    The title, the panel as raw HTML, the BibTeX dropdown, and the "Try it
    with mirdata" code.
    """
    name = data.get("name", fallback_name)
    panel = "\n".join(
        [
            overview(data),
            at_a_glance(data),
            statistics(data.get("stats")),
            combine_facts(data),
        ]
    )
    card = f"""{name}
{'-' * len(name)}

.. raw:: html

{textwrap.indent(panel, "   ")}
"""

    bibtex = data.get("bibtex")
    if bibtex and bibtex.strip():
        indented_bibtex = textwrap.indent(bibtex.strip(), "      ")
        card += f"""
.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

{indented_bibtex}
"""

    card += f"""
.. raw:: html

   <h3 class="panel-heading">Try it with mirdata</h3>

.. code-block:: python
   :class: try-mirdata
   :linenos:

{textwrap.indent(try_it(name, data.get("stats")), "   ")}
"""
    return card


def overview(data):
    summary = data.get("summary")
    text = (
        html.escape(summary)
        if summary
        else '<span class="panel-missing">No summary yet.</span>'
    )
    return (
        f'<h3 class="panel-heading">Overview</h3>\n<p class="panel-summary">{text}</p>'
    )


def at_a_glance(data):
    """The box of quick facts, with the annotation tags at the bottom. "—" marks a missing value."""
    stats = data.get("stats") or {}
    audio = stats.get("audio") or {}
    tracks = track_count(stats)
    sample_rate = audio.get("sample_rate")
    tags = data.get("annotations") or []
    license_text = " ".join((data.get("license") or "").split())

    rows = [
        glance_row("Tracks", f"{tracks:,}" if tracks is not None else None),
        glance_row(
            "Sample rate", f"{sample_rate / 1000:g} kHz" if sample_rate else None
        ),
        glance_row("Total duration", duration(audio.get("total_seconds"))),
        # gallery.js replaces the full text with its short license label
        glance_row(
            "License",
            license_text,
            f' data-license="{html.escape(license_text)}"',
        ),
        glance_row("Tasks", ", ".join(data.get("tasks") or [])),
    ]
    rows = "\n".join(rows)
    tag_html = "\n".join(
        f'<code data-ann="{html.escape(t)}">{html.escape(t)}</code>' for t in tags
    )
    return f"""<div class="panel-box">
<div class="box-title">At a glance</div>
<div class="glance-grid">
{rows}
</div>
<div class="box-title">Annotation types</div>
<div class="glance-tags">
{tag_html or "—"}
</div>
</div>"""


def track_count(stats):
    """The number of tracks: the audio's count, else the annotations' (None when unknown)."""
    audio = stats.get("audio") or {}
    return audio.get("n_tracks", (stats.get("annotations") or {}).get("n_tracks"))


def combine_facts(data):
    """What Combine mode (gallery.js, combine.js) adds up from this card, as JSON on a hidden element.

    The numbers behind the At a glance rows (None where the row shows "—"),
    the tasks, and the notes the Statistics box shows.
    """
    stats = data.get("stats") or {}
    audio = stats.get("audio") or {}
    facts = {
        "tracks": track_count(stats),
        "seconds": audio.get("total_seconds") or None,
        "sample_rate": audio.get("sample_rate") or None,
        "tasks": data.get("tasks") or [],
        "notes": stats_notes(data.get("stats")),
    }
    return f'<div class="panel-facts" hidden data-facts="{html.escape(json.dumps(facts))}"></div>'


def glance_row(label, value, value_attributes=""):
    return (
        f'<div class="glance-row"><span class="glance-label">{label}</span>'
        f'<span class="glance-value"{value_attributes}>{html.escape(value or "—")}</span></div>'
    )


def duration(seconds):
    """'6.7 hours' from one hour up, else '23.6 min'; None when unknown."""
    if not seconds:
        return None
    if seconds >= 3600:
        return f"{seconds / 3600:.1f} hours"
    return f"{seconds / 60:.1f} min"


def try_it(name, stats):
    """The "Try it with mirdata" code: get a track, then one line per annotation property the stats found.

    No download: it shows what a track gives access to. The lines are grouped
    by type (the order of the annotation tags), A–Z inside a type, each with
    its type as a comment, plus the part names (up to MAX_PARTS) when the
    property holds several annotations. Without stats, only the track.
    """
    lines = [
        "import mirdata",
        f'dataset = mirdata.initialize("{name}")',
        "track = dataset.choice_track()",
    ]
    entries = ((stats or {}).get("annotations") or {}).get("annotations") or {}
    access = sorted(
        (entry["type"], f"track.{prop}", list(entry.get("parts") or {}))
        for prop, entry in entries.items()
    )
    if access:
        width = max(len(code) for _, code, _ in access)
        lines.append("")
        for ann_type, code, parts in access:
            comment = ann_type
            if parts:
                more = ", …" if len(parts) > MAX_PARTS else ""
                comment += f", one per: {', '.join(parts[:MAX_PARTS])}{more}"
            lines.append(f"{code.ljust(width)}  # {comment}")
    return "\n".join(lines)


# --- Statistics --------------------------------------------------------------


def statistics(stats):
    """The Statistics box: status notes, then every plot."""
    out = ['<div class="panel-box">', '<div class="box-title">Statistics</div>']
    out.extend(note(text) for text in stats_notes(stats))
    plots = ordered_plots(stats) if stats and "error" not in stats else []
    if plots:
        out.append(plot_grid(plots))
    out.append("</div>")
    return "\n".join(out)


def stats_notes(stats):
    """The notes above the plots: no statistics, or not all of them, or nothing to plot."""
    if not stats:
        return ["No statistics yet."]
    if "error" in stats:
        return ["Statistics unavailable."]
    notes = status_notes(stats)
    if not ordered_plots(stats):
        notes.append("Nothing to plot yet.")
    return notes


def note(text):
    return f'<p class="stats-note">{html.escape(text)}</p>'


def status_notes(stats):
    """One line per part that is not ok: unavailable, or computed from fewer tracks."""
    notes = []
    for part, label in (("audio", "Audio"), ("annotations", "Annotation")):
        value = stats.get(part)
        if not value or value.get("status") == "ok":
            continue
        if value.get("status") == "error":
            notes.append(f"{label} statistics unavailable.")
            continue
        reason = (
            "some files need a local run"
            if value.get("status") == "needs_local"
            else "some files could not be read"
        )
        loaded, total = value.get("n_tracks_loaded"), value.get("n_tracks")
        if loaded is not None and total and loaded < total:
            notes.append(f"Computed from {loaded:,} of {total:,} tracks ({reason}).")
        else:
            notes.append(f"{label} statistics are incomplete ({reason}).")
    return notes


def ordered_plots(stats):
    """Every histogram and counts field to plot, in display order.

    The audio duration comes first, then the plots grouped by annotation type,
    A–Z. Inside a type, the entry (track property) with the most annotations
    comes first, then the others; each entry's plots in the schema's field
    order. An annotated tempo (TempoData) replaces the tempo derived from beats.
    """
    plots = []
    audio = stats.get("audio") or {}
    if is_histogram(audio.get("duration_histogram")):
        plots.append(
            plot(
                "duration_histogram",
                audio["duration_histogram"],
                "audio",
                audio.get("n_tracks"),
            )
        )

    by_type = {}
    entries = (stats.get("annotations") or {}).get("annotations") or {}
    annotated_tempo = any(
        e["type"] == "TempoData" and is_histogram(e.get("tempo"))
        for e in entries.values()
    )
    skip = {"tempo_from_beats"} if annotated_tempo else set()
    for prop, entry in entries.items():
        entry_plots = annotation_plots(prop, entry, skip)
        if entry_plots:
            by_type.setdefault(entry["type"], []).append((prop, entry, entry_plots))

    for ann_type in sorted(by_type):
        candidates = by_type[ann_type]
        best = max(
            candidates, key=lambda c: c[1].get("n_annotations", 0)
        )  # first one wins a tie
        plots.extend(best[2])
        plots.extend(
            p
            for prop, _, entry_plots in candidates
            if prop != best[0]
            for p in entry_plots
        )
    return plots


def annotation_plots(prop, entry, skip=()):
    """The plots of one annotation entry, its histograms and counts in the schema's field order, but the fields in skip."""
    order = list(STATS_ANNOTATION_FIELDS.get(entry["type"], {}))
    # counts only when the schema names them: "parts" is counts too, but not a plot
    fields = [
        key
        for key, value in entry.items()
        if key not in skip
        and (is_histogram(value) or (key in order and is_counts(value)))
    ]
    fields.sort(key=lambda key: order.index(key) if key in order else len(order))
    return [
        plot(
            key,
            entry[key],
            f"{prop} · {entry['type']}",
            entry.get("n_tracks"),
            entry.get("n_annotations"),
        )
        for key in fields
    ]


def is_histogram(value):
    return (
        isinstance(value, dict)
        and set(value) == {"unit", "edges", "counts"}
        and bool(value["counts"])
    )


def is_counts(value):
    """{label: count} with at least one count above 0."""
    return (
        isinstance(value, dict)
        and bool(value)
        and all(isinstance(v, int) for v in value.values())
        and any(value.values())
    )


def plot(field, data, source, n_tracks=None, n_annotations=None):
    """What one plot needs: data is a histogram or counts. counted names what the bars count, for the hover text."""
    total = sum(data["counts"]) if is_histogram(data) else sum(data.values())
    counted = (
        "tracks"
        if total == n_tracks
        else "annotations" if total == n_annotations else "values"
    )
    words = (
        field.removesuffix("_histogram")
        .removesuffix("_per_annotation")
        .replace("_", " ")
    )
    return {
        "title": words[:1].upper() + words[1:],
        "source": source,
        "data": data,
        "counted": counted,
    }


def plot_grid(plots):
    """The grid of plots, empty: charts.js draws them in the page from its data-plots.

    data-plots is the plots as JSON. A counts field goes as [label, count]
    pairs, so number labels (meter, polyphony) stay numbers.
    """
    data = [
        {
            **p,
            "data": p["data"] if is_histogram(p["data"]) else list(p["data"].items()),
        }
        for p in plots
    ]
    return f'<div class="plot-grid" data-plots="{html.escape(json.dumps(data))}"></div>'


# --- Directive ---------------------------------------------------------------


def _list_cards(cards_dir):
    return sorted(f for f in os.listdir(cards_dir) if f.endswith(".yaml"))


def _snapshot(cards_dir):
    """(filename, mtime) pairs for every card; used to detect added/removed cards."""
    try:
        names = _list_cards(cards_dir)
    except OSError:
        return None
    return tuple((f, os.path.getmtime(os.path.join(cards_dir, f))) for f in names)


class DatasetGallery(SphinxDirective):
    """``.. dataset-gallery:: <dir>`` — one section per YAML card in <dir>."""

    required_arguments = 1
    final_argument_whitespace = True

    def run(self):
        cards_arg = self.arguments[0]
        _, cards_dir = self.env.relfn2path(cards_arg)
        if not os.path.isdir(cards_dir):
            raise self.error(f"dataset-gallery: directory not found: {cards_dir}")

        # The page is built by this file and the card format it reads: editing
        # either re-renders the page too, not only editing a card.
        self.env.note_dependency(os.path.abspath(__file__))
        self.env.note_dependency(os.path.abspath(card_schema.__file__))

        # Same per-line normalisation (tab expansion, rstrip) Sphinx applies
        # when it reads an .rst file, so the output matches a file-based page.
        tab_width = self.state.document.settings.tab_width

        lines = []
        items = []  # (source, line) per line, so warnings point at the card file
        for fname in _list_cards(cards_dir):
            abs_path = os.path.join(cards_dir, fname)
            self.env.note_dependency(abs_path)

            with open(abs_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            card = render_card(data, fname[:-5])
            card_lines = string2lines(card, tab_width, convert_whitespace=True) + [""]
            lines.extend(card_lines)
            items.extend((abs_path, i) for i in range(len(card_lines)))

        # Remember what we saw so env-get-outdated can detect added/removed cards.
        if not hasattr(self.env, "gallery_cards"):
            self.env.gallery_cards = {}
        self.env.gallery_cards[self.env.docname] = (cards_dir, _snapshot(cards_dir))

        node = nodes.section()
        node.document = self.state.document
        nested_parse_with_titles(self.state, StringList(lines, items=items), node)
        return node.children


# --- Environment hooks -------------------------------------------------------


def get_outdated_docs(app, env, added, changed, removed):
    stored = getattr(env, "gallery_cards", {})
    already = added | changed | removed
    return [
        docname
        for docname, (cards_dir, snap) in stored.items()
        if docname not in already and _snapshot(cards_dir) != snap
    ]


def purge_doc(app, env, docname):
    if hasattr(env, "gallery_cards"):
        env.gallery_cards.pop(docname, None)


def merge_info(app, env, docnames, other):
    if not hasattr(env, "gallery_cards"):
        env.gallery_cards = {}
    env.gallery_cards.update(getattr(other, "gallery_cards", {}))


def setup(app):
    app.add_directive("dataset-gallery", DatasetGallery)
    app.connect("env-get-outdated", get_outdated_docs)
    app.connect("env-purge-doc", purge_doc)
    app.connect("env-merge-info", merge_info)
    return {"version": "0.1", "parallel_read_safe": True, "parallel_write_safe": True}
