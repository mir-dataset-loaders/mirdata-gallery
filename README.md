<img width="1618" height="500" alt="Screenshot 2026-09-14 at 3 58 18 PM" src="https://github.com/user-attachments/assets/06076d36-9fcc-4c77-8c82-db26f22f3be9" />


# mirdata Gallery
A repository for generating and maintaining structured YAML metadata for all datasets supported by the [`mirdata`](https://github.com/mir-dataset-loaders/mirdata) Python library. These YAML files serve as the **initial** data source for the `mirdata` dataset gallery 
For the gallery itself - the yaml files can be for the dataset cards, but also be the source of truth for filtering, when we define the scope of the attributes in need of filtering.

to run in dev mode:

```
source .venv/bin/activate

sphinx-build -b html docs docs/_build/html

```



## Pipeline & Scripts Overview
The gallery build pipeline consists of two primary scripts:
### 1. `utils/make_dataset_gallery_yaml.py` (Metadata Scraper)
Scrapes dataset metadata from the `mirdata` codebase into `dataset_yamls/*.yaml`:
* **Standardized Annotation Types:** Inspects track properties (both `@cached_property` and standard `@property`) using Python type annotations to map returns directly to `mirdata.annotations` classes (e.g. `BeatData`, `NoteData`, `F0Data`, `ChordData`).
* **Fallback & Classification Support:** Includes keyword matching list for untyped loaders, captures classification tasks (e.g. `Instrument`, `Genre`).
* **Defensive Sanitation:** Cleans and strips license strings and docstrings to prevent multiline formatting inconsistencies.
### 2. `utils/generate_gallery_cards.py` (Sphinx Card Generator)
Converts all `dataset_yamls/*.yaml` files into structured reStructuredText (`docs/index.rst`):
* **Tag & Download Formatting:** Renders annotations as code badges and links downloadable remotes.
* **Collapsible Dropdowns:** Packages detailed dataset docstrings, citations, and download instructions into Sphinx dropdown admonitions.
* **Single-Line Normalization:** Collapses whitespace and license descriptions to ensure clean Sphinx HTML list rendering.
### 3. `utils/summarize_datasets_llm.py` 
Takes the about docstring (unformatted throughout datasets) and formats it - current state - too short.
**TODO**
* Perhaps combine the processes of yaml generation and the summary generation(llm).
* Decide important aspects in the summary we wish to include and change the prompt accordingly.
* 
---
## Full Build Workflow
```bash
# 1. Scrape metadata from mirdata into YAMLs
python utils/make_dataset_gallery_yaml.py
# 2. Compile YAMLs into docs/index.rst cards
python utils/generate_gallery_cards.py
# 3. Build Sphinx HTML documentation
sphinx-build -b html docs docs/_build/html
```



## Example of output yaml
```
name: beatles
license: Not specified
remotes:
- annotations
annotations:
- BeatData
- ChordData
- KeyData
- SectionData
download_info: |2
  ...
bibtex: |-
  @inproceedings{mauch2009beatles,
  ...

```

