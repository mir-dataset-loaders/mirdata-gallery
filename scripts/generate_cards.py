"""Generate one YAML card per mirdata dataset.

Usage:
    python scripts/generate_cards.py                     # every dataset -> cards/
    python scripts/generate_cards.py --dataset beatles   # just one
    python scripts/generate_cards.py --output some/dir

The field functions live in card_fields.py and the YAML read/write in
cards_io.py; this file only wires them together.
"""

import argparse
import os

import mirdata

import card_fields
import cards_io


def build_card(ds):
    """The card dict for one initialized dataset; keys in card order."""
    return {
        "name": ds.name,
        "license": card_fields.license(ds),
        "annotations": card_fields.annotations(ds),
        "bibtex": card_fields.bibtex(ds),
        "docstring": card_fields.docstring(ds),
    }


def generate(names, output_dir):
    """Write a card for each dataset name. Returns (written, skipped)."""
    os.makedirs(output_dir, exist_ok=True)
    written = []
    skipped = {}

    print(f"Scanning {len(names)} dataset(s) in mirdata...")
    for name in names:
        try:
            ds = mirdata.initialize(name)
            card = build_card(ds)
        except ModuleNotFoundError as e:
            missing = str(e).replace("No module named ", "").strip("'")
            skipped[name] = f"missing library: {missing}"
            print(f"  [SKIP]  {name:30s} | needs: {missing}")
            continue
        except Exception as e:
            skipped[name] = str(e)
            print(f"  [ERROR] {name:30s} | {e}")
            continue

        cards_io.write_card(cards_io.card_path(output_dir, name), card)
        written.append(name)
        print(f"  [OK]    {name:30s} | annotations: {len(card['annotations'])}")

    print(f"\nDone. Written: {len(written)}, skipped: {len(skipped)}")
    return written, skipped


def main():
    parser = argparse.ArgumentParser(
        description="Generate dataset cards for the mirdata gallery."
    )
    parser.add_argument(
        "--output",
        default="cards",
        help="Directory for the YAML files (default: cards)",
    )
    parser.add_argument(
        "--dataset", default=None, help="Generate a single dataset only"
    )
    args = parser.parse_args()

    names = mirdata.list_datasets()
    if args.dataset:
        if args.dataset not in names:
            raise SystemExit(f"Dataset '{args.dataset}' not found in mirdata.")
        names = [args.dataset]

    generate(names, args.output)


if __name__ == "__main__":
    main()
