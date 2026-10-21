# Configuration file for the Sphinx documentation builder.
#
# For a full list of options see:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys

# Local extensions (the dataset-gallery directive lives in _ext/gallery.py)
sys.path.insert(0, os.path.abspath("_ext"))
# tests/card_schema.py: the card format, read by _ext/gallery.py for the order of the plots
sys.path.insert(0, os.path.abspath("../tests"))

# -- Project information -----------------------------------------------------

project = "mirdata"
copyright = "2026 mirdata development team"
author = "mirdata"

# FIXME: Need to display mirdata.version

# -- General configuration ---------------------------------------------------

extensions = [
    "sphinx_togglebutton",
    "sphinx_copybutton",
    "gallery",  # .. dataset-gallery:: directive, renders cards/*.yaml
]

togglebutton_hint = ""
togglebutton_hint_hide = ""

# The suffix of source filenames.
source_suffix = ".rst"

# The master toctree document.
master_doc = "index"

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- Options for HTML output -------------------------------------------------

html_theme = "sphinxawesome_theme"
html_title = "Mirdata Gallery"  # shown in the header next to the logo
html_logo = "img/mirdata.png"
html_permalinks = False  # no ¶ link after the headings
html_theme_options = {
    "main_nav_links": {"Home": "index", "Gallery": "gallery"},  # header links
    "show_breadcrumbs": False,  # two pages; the header links are the navigation
}
# The front page has no left sidebar (on the gallery page, gallery.js puts the filters there)
html_sidebars = {"index": []}

# Custom static files, copied after the theme's own so they can override it.
html_static_path = ["_static"]
html_css_files = ["css/custom.css"]
html_js_files = ["js/light-mode.js", "js/charts.js", "js/combine.js", "js/gallery.js"]
