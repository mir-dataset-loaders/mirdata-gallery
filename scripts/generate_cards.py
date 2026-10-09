"""Generate one YAML card per mirdata dataset.

Usage:
    python scripts/generate_cards.py                     # every dataset -> cards/
    python scripts/generate_cards.py --dataset beatles   # just one
    python scripts/generate_cards.py --missing           # only datasets with no card yet
    python scripts/generate_cards.py --no-summary        # skip the LLM, keep old summaries
    python scripts/generate_cards.py --output some/dir

The field functions live in card_fields.py, the LLM summary in llm.py and the
YAML read/write in cards_io.py; this file only wires them together.
"""

import argparse
import os

import mirdata

import card_fields
import cards_io
import llm


def build_card(ds, summarize=True):
    """The card dict for one initialized dataset; keys in card order."""
    return {
        "name": ds.name,
        "license": card_fields.license(ds),
        "annotations": card_fields.annotations(ds),
        "bibtex": card_fields.bibtex(ds),
        "summary": llm.summary(ds) if summarize else None,
    }


def generate(names, output_dir, summarize=True):
    """Write a card for each dataset name. Returns (written, skipped).

    With summarize=False the LLM is not run and each card keeps the summary
    it already has (or gets null).
    """
    os.makedirs(output_dir, exist_ok=True)
    written = []
    skipped = {}

    print(f"Scanning {len(names)} dataset(s) in mirdata...")
    for name in names:
        try:
            ds = mirdata.initialize(name)
            card = build_card(ds, summarize)
        except ModuleNotFoundError as e:
            missing = str(e).replace("No module named ", "").strip("'")
            skipped[name] = f"missing library: {missing}"
            print(f"  [SKIP]  {name:30s} | needs: {missing}")
            continue
        except Exception as e:
            skipped[name] = str(e)
            print(f"  [ERROR] {name:30s} | {e}")
            continue

        path = cards_io.card_path(output_dir, name)
        if not summarize:
            card["summary"] = (cards_io.read_card(path) or {}).get("summary")
        cards_io.write_card(path, card)
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
    parser.add_argument(
        "--missing",
        action="store_true",
        help="Only datasets that have no card in the output directory yet",
    )
    parser.add_argument(
        "--no-summary",
        action="store_true",
        help="Skip the LLM summary; cards keep the summary they already have",
    )
    args = parser.parse_args()

    names = mirdata.list_datasets()
    if args.dataset:
        if args.dataset not in names:
            raise SystemExit(f"Dataset '{args.dataset}' not found in mirdata.")
        names = [args.dataset]
    elif args.missing:
        names = [
            n for n in names if not os.path.exists(cards_io.card_path(args.output, n))
        ]
        if not names:
            print("Every mirdata dataset already has a card.")
            return
        print(f"Datasets without a card: {', '.join(names)}")

    generate(names, args.output, summarize=not args.no_summary)


if __name__ == "__main__":
    main()
