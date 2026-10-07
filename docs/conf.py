# Configuration file for the Sphinx documentation builder.
#
# For a full list of options see:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys

# Local extensions (the dataset-gallery directive lives in _ext/gallery.py)
sys.path.insert(0, os.path.abspath("_ext"))

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

html_theme = "sphinx_rtd_theme"
html_logo = "img/mirdata.png"

# Custom static files, copied after the theme's own so they can override it.
html_static_path = ["_static"]
html_css_files = ["css/custom.css"]
html_js_files = ["js/gallery.js"]
