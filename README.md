<img width="1618" height="500" alt="Screenshot 2026-09-14 at 3 58 18 PM" src="https://github.com/user-attachments/assets/06076d36-9fcc-4c77-8c82-db26f22f3be9" />


# mirdata Gallery

A browsable gallery of every dataset supported by the [`mirdata`](https://github.com/mir-dataset-loaders/mirdata) Python library. Each dataset is described by one YAML card in `cards/`, scraped from the mirdata loaders. The cards are the single data source: a Sphinx extension renders them into the gallery page at build time, and the filter sidebar is built from the same values.

## Folder structure

```
mirdata-gallery/
├── cards/                        # one YAML per dataset; the data the site is built from
├── scripts/
│   ├── generate_cards.py         # pipeline: mirdata loaders -> cards/*.yaml
│   ├── card_fields.py            # one function per card field
│   ├── cards_io.py               # read/write cards with one YAML style
│   └── summarize_datasets_llm.py # needs to be fixed
├── tests/
│   ├── card_schema.py            # the card schema: fields and rules
│   └── test_cards_schema.py      
├── docs/
│   ├── index.rst                 # the only page; uses the dataset-gallery directive
│   ├── conf.py                   # Sphinx config
│   ├── _ext/gallery.py           # directive that renders cards at build time
│   ├── _static/                  # css (badge colours) and js (filter sidebar)
│   ├── img/
│   └── requirements.txt        
├── requirements.txt             
├── .readthedocs.yml
└── README.md
```

## Setup


```bash
pip install -r requirements.txt -r docs/requirements.txt
```


To check the setup, build the site and open `docs/_build/html/index.html`:

```bash
sphinx-build -b html docs docs/_build/html
```
