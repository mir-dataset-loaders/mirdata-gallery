"""Record the current docstring hash for every card that has a summary.

Run once before the first workflow run so existing summaries count as up to
date; otherwise the LLM would redo all of them. No LLM is run here.

Usage:
    python scripts/init_hashes.py                     # every dataset -> cards/docstring_hashes.json
    python scripts/init_hashes.py --dataset beatles   # just one
    python scripts/init_hashes.py --output some/dir
"""

import argparse

import mirdata

import card_utils
import llm
import stats.utils


def init_hashes(names, output_dir):
    """Record the current docstring hash for every card that has a summary.

    Run once before the first workflow run so existing summaries count as
    up to date; otherwise the LLM would redo all of them.
    """
    updated = card_utils.read_hashes(output_dir)
    count = 0
    for name in names:
        card = card_utils.read_card(card_utils.card_path(output_dir, name)) or {}
        if not card.get("summary"):
            continue
        try:
            docstring = llm.loader_docstring(name)
        except ModuleNotFoundError as e:
            print(f"  [SKIP]  {name:30s} | needs: {e.name}")
            continue
        if docstring:
            updated[name] = card_utils.docstring_hash(docstring)
            count += 1
    card_utils.write_hashes(output_dir, updated)
    print(f"Recorded {count} hash(es) in {card_utils.hashes_path(output_dir)}")


def main():
    parser = argparse.ArgumentParser(
        description="Record docstring hashes for cards that have a summary; no LLM."
    )
    parser.add_argument(
        "--output",
        default="cards",
        help="Directory of the YAML files and the hashes (default: cards)",
    )
    parser.add_argument(
        "--dataset", default=None, help="Record a single dataset only"
    )
    args = parser.parse_args()

    names = stats.utils.select_datasets(mirdata.list_datasets(), args.dataset)
    init_hashes(names, args.output)


if __name__ == "__main__":
    main()
