"""Generate one YAML card per mirdata dataset.

Usage:
    python scripts/generate_cards.py                     # every dataset -> cards/
    python scripts/generate_cards.py --dataset beatles   # just one
    python scripts/generate_cards.py --missing           # only datasets with no card yet
    python scripts/generate_cards.py --no-summary        # skip the LLM, keep old summaries
    python scripts/generate_cards.py --force             # redo every summary
    python scripts/generate_cards.py --init-hashes       # one-time: record hashes, no LLM
    python scripts/generate_cards.py --output some/dir

Every run rebuilds the cheap fields (license, annotations, bibtex) from the
installed mirdata, so a card changes exactly when the loader's information
changed. The summary is reused unless the loader docstring hashes differently
from the one recorded in cards/docstring_hashes.json (see hashes.py).

The field functions live in card_fields.py, the LLM summary in llm.py, the
YAML read/write in cards_io.py; this file only wires them together.
"""

import argparse
import os

import mirdata

import card_fields
import cards_io
import hashes
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


def generate(names, output_dir, summarize=True, force=False):
    """Write a card for each dataset name. Returns (written, skipped).

    The LLM runs only for datasets whose docstring hash is new or changed
    (or for all of them with force=True). With summarize=False it never runs
    and each card keeps the summary it already has (or gets null).
    """
    os.makedirs(output_dir, exist_ok=True)
    stored = hashes.read(output_dir)
    updated = dict(stored)
    written = []
    skipped = {}

    print(f"Scanning {len(names)} dataset(s) in mirdata...")
    for name in names:
        path = cards_io.card_path(output_dir, name)
        old = cards_io.read_card(path) or {}
        try:
            ds = mirdata.initialize(name)
            docstring = llm.loader_docstring(name)
            current = hashes.of(docstring) if docstring else None
            redo = summarize and bool(docstring) and (
                force or current != stored.get(name) or not old.get("summary")
            )
            card = build_card(ds, summarize=redo)
        except ModuleNotFoundError as e:
            missing = str(e).replace("No module named ", "").strip("'")
            skipped[name] = f"missing library: {missing}"
            print(f"  [SKIP]  {name:30s} | needs: {missing}")
            continue
        except Exception as e:
            skipped[name] = str(e)
            print(f"  [ERROR] {name:30s} | {e}")
            continue

        if redo:
            updated[name] = current
            status = "new"
        elif docstring or not summarize:
            card["summary"] = old.get("summary")
            status = "kept"
        else:  # loader has no docstring (any more): no summary, no hash
            updated.pop(name, None)
            status = "none"

        cards_io.write_card(path, card)
        written.append(name)
        print(
            f"  [OK]    {name:30s} | annotations: {len(card['annotations'])}"
            f" | summary: {status}"
        )

    if updated != stored:
        hashes.write(output_dir, updated)
    print(f"\nDone. Written: {len(written)}, skipped: {len(skipped)}")
    return written, skipped


def init_hashes(names, output_dir):
    """Record the current docstring hash for every card that has a summary.

    Run once before the first workflow run so existing summaries count as
    up to date; otherwise the LLM would redo all of them.
    """
    updated = hashes.read(output_dir)
    count = 0
    for name in names:
        card = cards_io.read_card(cards_io.card_path(output_dir, name)) or {}
        if not card.get("summary"):
            continue
        try:
            docstring = llm.loader_docstring(name)
        except ModuleNotFoundError as e:
            print(f"  [SKIP]  {name:30s} | needs: {e.name}")
            continue
        if docstring:
            updated[name] = hashes.of(docstring)
            count += 1
    hashes.write(output_dir, updated)
    print(f"Recorded {count} hash(es) in {hashes.path(output_dir)}")


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
    parser.add_argument(
        "--force",
        action="store_true",
        help="Redo every summary even if the docstring is unchanged",
    )
    parser.add_argument(
        "--init-hashes",
        action="store_true",
        help="Only record docstring hashes for cards that have a summary; no LLM",
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

    if args.init_hashes:
        init_hashes(names, args.output)
        return

    generate(names, args.output, summarize=not args.no_summary, force=args.force)


if __name__ == "__main__":
    main()
