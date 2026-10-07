"""Sphinx extension: render the mirdata dataset gallery straight from the cards.

Usage in an .rst file::

    .. dataset-gallery:: ../cards

The argument is the directory holding one YAML card per dataset, relative to
the current document. Each card becomes a section with the markup that
``scripts/generate_gallery_cards.py`` used to write into ``index.rst``, so the
resulting HTML (and therefore ``gallery.js`` / ``custom.css``) is unchanged.

Every card is registered as a dependency of the page, and the directory is
snapshotted, so editing, adding or removing a card makes Sphinx re-read the
page on the next incremental build without needing ``-E``.
"""

import os
import posixpath
import textwrap

import yaml
from docutils import nodes
from docutils.statemachine import StringList, string2lines
from sphinx.util import logging
from sphinx.util.docutils import SphinxDirective
from sphinx.util.nodes import nested_parse_with_titles

logger = logging.getLogger(__name__)

# FIXME: should revisit this script. just pulled from make_index.py

# --- Card rendering ----------------------------------------------------------


def render_card(data, yaml_relpath, fallback_name):
    """Return the RST for one dataset card.

    ``yaml_relpath`` is the card's path relative to the current document; it is
    used for the :download: link and the literalinclude.
    """
    yaml_name = posixpath.basename(yaml_relpath)

    name = data.get("name", fallback_name)
    license_str = data.get("license", "Not specified")
    if isinstance(license_str, str):
        # Collapse multi-line/whitespace into a single clean line
        license_str = " ".join(license_str.split())

    # 1. Format annotations as inline code tags
    annotations_list = data.get("annotations")
    if annotations_list and isinstance(annotations_list, list):
        annotations_str = ", ".join(f"``{a}``" for a in annotations_list)
    else:
        annotations_str = "*None*"

    # 2. Format remotes / downloadable components
    remotes_list = data.get("remotes")
    if remotes_list and isinstance(remotes_list, list):
        remotes_str = ", ".join(f"``{r}``" for r in remotes_list)
    else:
        remotes_str = "*No direct download available*"

    card = f"""{name}
{'-' * len(name)}


* **Annotations:** {annotations_str}

"""

    # 3. "About this dataset": LLM summary if present, else the cleaned docstring
    docstring = data.get("docstring")
    if docstring and docstring.strip():
        filtered = []
        for line in docstring.strip().splitlines():
            stripped = line.strip()
            # Remove redundant ".. admonition::", ":class:", and "<Dataset> Loader" headers
            if stripped.startswith(".. admonition::") or stripped.startswith(":class:"):
                continue
            if stripped.endswith("Loader") and len(stripped.split()) <= 4:
                continue
            filtered.append(line)

        clean_doc = textwrap.dedent("\n".join(filtered)).strip()
        about_text = data.get("summary") or clean_doc

        card += f"""
**About this dataset:**

{about_text}

"""

    # 4. License, remotes & YAML download
    card += f"""* **License:** {license_str}
* **Downloadable Remotes:** {remotes_str}
* **YAML File:** :download:`{yaml_name}<{yaml_relpath}>`

"""

    # 5. Download instructions dropdown
    download_info = data.get("download_info")
    if download_info and download_info.strip():
        # Detect if download_info contains a file tree
        tree_markers = ["├──", "|--", "└──", "> "]
        if any(marker in download_info for marker in tree_markers):
            formatted_lines = []
            tree_started = False
            for line in download_info.strip().splitlines():
                if not tree_started and (
                    line.startswith("    ") or any(m in line for m in tree_markers)
                ):
                    formatted_lines.extend(["", "::", ""])
                    tree_started = True
                formatted_lines.append(line)
            download_info = "\n".join(formatted_lines)

        indented_download = textwrap.indent(download_info.strip(), "   ")
        card += f"""
.. admonition:: Download Instructions
   :class: dropdown


{indented_download}
"""

    # 6. BibTeX dropdown
    bibtex = data.get("bibtex")
    if bibtex and bibtex.strip():
        indented_bibtex = textwrap.indent(bibtex.strip(), "      ")
        card += f"""
.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

{indented_bibtex}
"""

    # 7. Raw YAML, viewable inside a collapsible toggle
    card += f"""
.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: {yaml_relpath}
      :language: yaml
"""
    return card


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

            card = render_card(data, posixpath.join(cards_arg, fname), fname[:-5])
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
