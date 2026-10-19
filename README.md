# mirdata Gallery

This repo is still work in progress. 

A browsable gallery of every dataset supported by the [`mirdata`](https://github.com/mir-dataset-loaders/mirdata) Python library. Each dataset is described by one YAML card in `cards/`, scraped from the mirdata loaders. The cards are the single data source: a Sphinx extension renders them into the gallery page at build time, and the filter sidebar is built from the same values.


## Setup


```bash
pip install -r requirements.txt -r docs/requirements.txt
```


To check the setup, build the site and open `docs/_build/html/index.html`:

```bash
sphinx-build -b html docs docs/_build/html
```
