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
import os
import textwrap

import yaml
from card_schema import STATS_ANNOTATION_FIELDS
from docutils import nodes
from docutils.statemachine import StringList, string2lines
from sphinx.util import logging
from sphinx.util.docutils import SphinxDirective
from sphinx.util.nodes import nested_parse_with_titles

logger = logging.getLogger(__name__)

MAX_PLOTS = 3  # plots shown before "Show more"
UNIT_LABELS = {"hz": "Hz", "midi": "MIDI"}  # how a unit is written; others as stored

# Size of every chart, in SVG units (the chart scales to the width it gets).
# The margins leave room for the y labels (left) and the x labels and unit (bottom).
WIDTH, HEIGHT = 120, 90
LEFT, RIGHT, TOP, BOTTOM = 26, 12, 6, 24
MAX_TICKS = 3  # edge values written under the x axis

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
    text = html.escape(summary) if summary else '<span class="panel-missing">No summary yet.</span>'
    return f'<h3 class="panel-heading">Overview</h3>\n<p class="panel-summary">{text}</p>'


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
        glance_row("Sample rate", f"{sample_rate / 1000:g} kHz" if sample_rate else None),
        glance_row("Total duration", duration(audio.get("total_seconds"))),
        # gallery.js replaces the full text with its short license label
        glance_row(
            "License",
            license_text,
            f' data-license="{html.escape(license_text)}"',
        ),
        glance_row("Annotations", f"{len(tags)} type{'s' if len(tags) != 1 else ''}" if tags else None),
    ]
    rows = "\n".join(rows)
    tag_html = "\n".join(f'<code data-ann="{html.escape(t)}">{html.escape(t)}</code>' for t in tags)
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
    """The Statistics box: status notes, the first MAX_PLOTS plots, the rest behind "Show more"."""
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
            out.append(plot_grid(plots[:MAX_PLOTS]))
            if plots[MAX_PLOTS:]:
                out.append(show_more(plots[MAX_PLOTS:]))
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
    """Every histogram to plot, in display order.

    The audio duration comes first, then the first plot of each annotation type,
    then the rest of each type's plots. When several entries (track properties)
    have the same type, the one with the most annotations counts for its type;
    the others' plots come last.
    """
    plots = []
    audio = stats.get("audio") or {}
    if is_histogram(audio.get("duration_histogram")):
        plots.append(
            plot("duration_histogram", audio["duration_histogram"], "audio", audio.get("n_tracks"))
        )

    by_type = {}
    entries = (stats.get("annotations") or {}).get("annotations") or {}
    for prop, entry in entries.items():
        entry_plots = annotation_plots(prop, entry)
        if entry_plots:
            by_type.setdefault(entry["type"], []).append((prop, entry, entry_plots))

    firsts, rests, others = [], [], []
    for ann_type in sorted(by_type):
        candidates = by_type[ann_type]
        best = max(candidates, key=lambda c: c[1].get("n_annotations", 0))  # first one wins a tie
        firsts.append(best[2][0])
        rests.extend(best[2][1:])
        others.extend(p for prop, _, entry_plots in candidates if prop != best[0] for p in entry_plots)
    return plots + firsts + rests + others


def annotation_plots(prop, entry):
    """The plots of one annotation entry, its histograms in the schema's field order."""
    order = list(STATS_ANNOTATION_FIELDS.get(entry["type"], {}))
    fields = [key for key, value in entry.items() if is_histogram(value)]
    fields.sort(key=lambda key: order.index(key) if key in order else len(order))
    return [
        plot(key, entry[key], f"{prop} · {entry['type']}", entry.get("n_tracks"), entry.get("n_annotations"))
        for key in fields
    ]


def is_histogram(value):
    return isinstance(value, dict) and set(value) == {"unit", "edges", "counts"} and bool(value["counts"])


def plot(field, hist, source, n_tracks=None, n_annotations=None):
    """What one plot needs. counted names what the bars count, for the hover text."""
    total = sum(hist["counts"])
    counted = "tracks" if total == n_tracks else "annotations" if total == n_annotations else "values"
    words = field.removesuffix("_histogram").removesuffix("_per_annotation").replace("_", " ")
    return {"title": words[:1].upper() + words[1:], "source": source, "hist": hist, "counted": counted}


def plot_grid(plots):
    figures = "\n".join(
        f'<figure class="plot"><figcaption><span class="plot-title">{html.escape(p["title"])}</span>'
        f'<span class="plot-source">{html.escape(p["source"])}</span></figcaption>'
        f'{histogram_svg(p["hist"], p["counted"])}</figure>'
        for p in plots
    )
    return f'<div class="plot-grid">\n{figures}\n</div>'


def show_more(plots):
    """The rest of the plots, folded; the label reads "Show less" while open (custom.css)."""
    return (
        '<details class="plot-toggle"><summary><span class="when-closed">Show more</span>'
        f'<span class="when-open">Show less</span></summary>\n{plot_grid(plots)}\n</details>'
    )


def number(x):
    """An edge value as written on the axis: 1,000 or 12.5."""
    return f"{int(x):,}" if float(x).is_integer() else f"{x:g}"


def histogram_svg(hist, counted):
    """One histogram {unit, edges, counts} as an SVG bar chart; the one chart every plot uses.

    The y axis shows 0 and the highest count, the x axis up to MAX_TICKS edge
    values and the unit. Hovering a bar shows its range and count.
    """
    edges, counts = hist["edges"], hist["counts"]
    unit = UNIT_LABELS.get(hist["unit"], hist["unit"])
    plot_width, plot_height = WIDTH - LEFT - RIGHT, HEIGHT - TOP - BOTTOM
    bar_width = plot_width / len(counts)
    highest = max(counts) or 1
    base = TOP + plot_height

    out = [f'<svg class="plot-svg" viewBox="0 0 {WIDTH} {HEIGHT}" role="img">']
    for i, count in enumerate(counts):
        x = LEFT + i * bar_width
        height = plot_height * count / highest
        tip = f"{number(edges[i])}–{number(edges[i + 1])} {unit}: {count:,} {counted}"
        out.append(
            f"<g><title>{html.escape(tip)}</title>"
            f'<rect class="plot-hit" x="{x:.1f}" y="{TOP}" width="{bar_width:.1f}" height="{plot_height}"/>'
            f'<rect class="plot-bar" x="{x + 0.5:.1f}" y="{base - height:.1f}"'
            f' width="{max(bar_width - 1, 0.5):.1f}" height="{height:.1f}"/></g>'
        )
    out.append(f'<line class="plot-axis" x1="{LEFT}" y1="{base}" x2="{WIDTH - RIGHT}" y2="{base}"/>')
    for y, label in ((TOP, f"{highest:,}"), (base, "0")):
        out.append(
            f'<text class="plot-label" x="{LEFT - 3}" y="{y}" text-anchor="end"'
            f' dominant-baseline="middle">{label}</text>'
        )
    step = -(-len(counts) // (MAX_TICKS - 1))  # every step-th edge, so labels are evenly spaced
    for i in range(0, len(edges), step):
        out.append(
            f'<text class="plot-label" x="{LEFT + i * bar_width:.1f}" y="{base + 10}"'
            f' text-anchor="middle">{number(edges[i])}</text>'
        )
    out.append(
        f'<text class="plot-unit" x="{LEFT + plot_width / 2:.1f}" y="{HEIGHT - 4}"'
        f' text-anchor="middle">{html.escape(unit)}</text>'
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
