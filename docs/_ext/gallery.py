"""Sphinx extension: render the mirdata dataset gallery straight from the cards.

Usage in an .rst file::

    .. dataset-gallery:: ../cards

The argument is the directory holding one YAML card per dataset, relative to
the current document. Each card becomes a section, the dataset's panel: its
title, an overview (the summary), an "At a glance" box, the statistics as SVG
bar charts, and the BibTeX citation. gallery.js arranges the sections into
the filterable gallery, custom.css styles them.

Every card is registered as a dependency of the page, and the directory is
snapshotted, so editing, adding or removing a card makes Sphinx re-read the
page on the next incremental build without needing ``-E``.
"""

import html
import itertools
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

UNIT_LABELS = {"hz": "Hz", "midi": "MIDI"}  # how a unit is written; others as stored

# Size of every chart, in SVG units (the chart scales to the width it gets).
# The margins leave room for the x labels and unit (bottom), for the y numbers
# (left), and for the last x label to stick out past the bars (right).
WIDTH, HEIGHT = 120, 98
LEFT, RIGHT, TOP, BOTTOM = 21, 12, 6, 32
MAX_TICKS = 3  # edge values written under the x axis
MAX_Y_TICKS = 4  # round numbers written left of the bars, each with a grid line
MIN_SLOTS = (
    8  # a chart with fewer bars keeps the bar width of this many, with wider gaps
)
MAX_LABELS = 10  # text labels plotted per counts field; the rest join "(other)"
MAX_LABEL_CHARS = 7  # a longer label is cut under its bar; the hover text has it whole
CHAR_WIDTH = 4.7  # about how wide one character of a plot label is, in SVG units
OTHER = "(other)"

# "Try it with mirdata": mirdata's README quickstart, the same for every dataset but its name
TRY_IT = """import mirdata
dataset = mirdata.initialize("{name}")
dataset.download()
dataset.validate()
track = dataset.choice_track()
print(track)"""

# --- Card rendering ----------------------------------------------------------


def render_card(data, fallback_name):
    """Return the RST for one dataset card.

    The title, the panel as raw HTML, the "Try it with mirdata" code, and the
    BibTeX dropdown.
    """
    name = data.get("name", fallback_name)
    panel = "\n".join(
        [
            overview(data),
            at_a_glance(data),
            statistics(data.get("stats")),
            '<h3 class="panel-heading">Try it with mirdata</h3>',
        ]
    )
    card = f"""{name}
{'-' * len(name)}

.. raw:: html

{textwrap.indent(panel, "   ")}

.. code-block:: python
   :class: try-mirdata
   :linenos:

{textwrap.indent(TRY_IT.format(name=name), "   ")}
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
    tracks = audio.get("n_tracks", (stats.get("annotations") or {}).get("n_tracks"))
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


# --- Statistics --------------------------------------------------------------


def statistics(stats):
    """The Statistics box: status notes, then every plot."""
    out = ['<div class="panel-box">', '<div class="box-title">Statistics</div>']
    if not stats:
        out.append(note("No statistics yet."))
    elif "error" in stats:
        out.append(note("Statistics unavailable."))
    else:
        out.extend(note(text) for text in status_notes(stats))
        plots = ordered_plots(stats)
        if not plots:
            out.append(note("Nothing to plot yet."))
        else:
            out.append(plot_grid(plots))
    out.append("</div>")
    return "\n".join(out)


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

    The audio duration comes first, then the first plot of each annotation type,
    then the rest of each type's plots. When several entries (track properties)
    have the same type, the one with the most annotations counts for its type;
    the others' plots come last. An annotated tempo (TempoData) replaces the
    tempo derived from beats.
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

    firsts, rests, others = [], [], []
    for ann_type in sorted(by_type):
        candidates = by_type[ann_type]
        best = max(
            candidates, key=lambda c: c[1].get("n_annotations", 0)
        )  # first one wins a tie
        firsts.append(best[2][0])
        rests.extend(best[2][1:])
        others.extend(
            p
            for prop, _, entry_plots in candidates
            if prop != best[0]
            for p in entry_plots
        )
    return plots + firsts + rests + others


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
            f"{entry['type']}",
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
    figures = "\n".join(
        f'<figure class="plot"><figcaption><span class="plot-title">{html.escape(p["title"])}</span>'
        f'<span class="plot-source">{html.escape(p["source"])}</span></figcaption>'
        f'{chart_svg(p["data"], p["counted"])}</figure>'
        for p in plots
    )
    return f'<div class="plot-grid">\n{figures}\n</div>'


def number(x):
    """An edge value as written on the axis: 1,000 or 12.5."""
    return f"{int(x):,}" if float(x).is_integer() else f"{x:g}"


def chart_svg(data, counted):
    return (
        histogram_svg(data, counted)
        if is_histogram(data)
        else counts_svg(data, counted)
    )


def y_ticks(highest):
    """The y ticks under the tallest bar: multiples of the smallest 1, 2 or 5 × 10ⁿ step giving at most MAX_Y_TICKS, without 0."""
    steps = (m * 10**e for e in itertools.count() for m in (1, 2, 5))
    step = next(s for s in steps if highest // s <= MAX_Y_TICKS)
    return [step * i for i in range(1, highest // step + 1)]


def short_number(n):
    """A y tick as written: 500, 1.5k, 20k, 1.5M."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:g}M"
    if n >= 1_000:
        return f"{n / 1_000:g}k"
    return str(n)


def bars_svg(counts, tips):
    """The part every chart shares: one bar per count, the x axis, and the y ticks (y_ticks), each a grid line behind the bars and a number; hovering shows the exact counts.

    Each bar has an equal slot of the x axis and sits in its middle. With fewer
    than MIN_SLOTS bars, a bar keeps the width it has in a chart of MIN_SLOTS
    bars, so a few bars are spread out instead of filling the chart. The
    tallest bar reaches the top.
    Returns the SVG pieces (without the closing tag), the slot width and the y of the axis.
    """
    plot_width, plot_height = WIDTH - LEFT - RIGHT, HEIGHT - TOP - BOTTOM
    slot = plot_width / len(counts)
    bar_width = plot_width / max(len(counts), MIN_SLOTS)
    highest = max(counts) or 1
    base = TOP + plot_height

    out = [f'<svg class="plot-svg" viewBox="0 0 {WIDTH} {HEIGHT}" role="img">']
    for tick in y_ticks(max(counts)):
        y = base - plot_height * tick / highest
        out.append(
            f'<line class="plot-gridline" x1="{LEFT}" y1="{y:.1f}" x2="{WIDTH - RIGHT}" y2="{y:.1f}"/>'
            f'<text class="plot-label plot-y-label" x="{LEFT - 2}" y="{y:.1f}" text-anchor="end"'
            f' dominant-baseline="middle">{short_number(tick)}</text>'
        )
    for i, (count, tip) in enumerate(zip(counts, tips)):
        x = LEFT + i * slot
        bar_x = x + (slot - bar_width) / 2
        height = plot_height * count / highest
        out.append(
            f"<g><title>{html.escape(tip)}</title>"
            f'<rect class="plot-hit" x="{x:.1f}" y="{TOP}" width="{slot:.1f}" height="{plot_height}"/>'
            f'<rect class="plot-bar" x="{bar_x + 0.5:.1f}" y="{base - height:.1f}"'
            f' width="{max(bar_width - 1, 0.5):.1f}" height="{height:.1f}"/></g>'
        )
    out.append(
        f'<line class="plot-axis" x1="{LEFT}" y1="{base}" x2="{WIDTH - RIGHT}" y2="{base}"/>'
    )
    return out, slot, base


def histogram_svg(hist, counted):
    """One histogram {unit, edges, counts} as an SVG bar chart.

    The x axis shows up to MAX_TICKS edge values and the unit. Hovering a bar
    shows its range and count.
    """
    edges, counts = hist["edges"], hist["counts"]
    unit = UNIT_LABELS.get(hist["unit"], hist["unit"])
    plot_width = WIDTH - LEFT - RIGHT
    tips = [
        f"{number(edges[i])}–{number(edges[i + 1])} {unit}: {count:,} {counted}"
        for i, count in enumerate(counts)
    ]
    out, slot, base = bars_svg(counts, tips)
    step = -(
        -len(counts) // (MAX_TICKS - 1)
    )  # every step-th edge, so labels are evenly spaced
    for i in range(0, len(edges), step):
        out.append(
            f'<text class="plot-label" x="{LEFT + i * slot:.1f}" y="{base + 10}"'
            f' text-anchor="middle">{number(edges[i])}</text>'
        )
    out.append(
        f'<text class="plot-unit" x="{LEFT + plot_width / 2:.1f}" y="{base + 20}"'
        f' text-anchor="middle">{html.escape(unit)}</text>'
    )
    out.append("</svg>")
    return "".join(out)


def count_bars(counts):
    """(label, count) per bar of a counts field.

    Numbers (meter, polyphony) are all plotted, in order. Text labels are
    plotted most common first, MAX_LABELS of them; the rest join "(other)".
    """
    if all(isinstance(k, int) for k in counts):
        return sorted(counts.items())
    named = sorted(
        ((str(k), v) for k, v in counts.items() if k != OTHER), key=lambda kv: -kv[1]
    )
    rest = sum(v for _, v in named[MAX_LABELS:]) + counts.get(OTHER, 0)
    return named[:MAX_LABELS] + ([(OTHER, rest)] if rest else [])


def counts_svg(counts, counted):
    """One counts field {label: count} as an SVG bar chart, the same chart as a histogram.

    Every bar has its label under it: flat when every label fits under its
    bar, else tilted, smaller and cut to MAX_LABEL_CHARS. Hovering a bar shows
    the whole label and its count.
    """
    bars = count_bars(counts)
    tips = [f"{label}: {count:,} {counted}" for label, count in bars]
    out, slot, base = bars_svg([count for _, count in bars], tips)
    labels = [str(label) for label, _ in bars]
    flat = all(len(label) * CHAR_WIDTH <= slot for label in labels)
    for i, label in enumerate(labels):
        x = LEFT + (i + 0.5) * slot
        if flat:
            out.append(
                f'<text class="plot-label" x="{x:.1f}" y="{base + 10}"'
                f' text-anchor="middle">{html.escape(label)}</text>'
            )
            continue
        text = (
            label
            if len(label) <= MAX_LABEL_CHARS
            else label[: MAX_LABEL_CHARS - 1] + "…"
        )
        y = base + 3
        out.append(
            f'<text class="plot-label plot-label-tilted" x="{x:.1f}" y="{y}" text-anchor="end"'
            f' dominant-baseline="middle" transform="rotate(-60 {x:.1f} {y})">{html.escape(text)}</text>'
        )
    out.append("</svg>")
    return "".join(out)


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
