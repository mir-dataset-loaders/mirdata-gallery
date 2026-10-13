"""Generate one YAML card per mirdata dataset.

Every run rebuilds the cheap fields (license, annotations, bibtex). The LLM
summary and the stats are recomputed only when needed: when the loader
docstring changed (cards/docstring_hashes.json) or the dataset index changed
(stored in the card). Datasets whose stats need a local run are listed at
the end.

Usage:
    python scripts/generate_cards.py                     # every dataset -> cards/
    python scripts/generate_cards.py --dataset beatles   # just one
    python scripts/generate_cards.py --missing           # only datasets with no card yet
    python scripts/generate_cards.py --no-summary        # skip the LLM, keep old summaries
    python scripts/generate_cards.py --force             # redo every summary
    python scripts/generate_cards.py --init-hashes       # one-time: record hashes, no LLM
    python scripts/generate_cards.py --output some/dir
    python scripts/generate_cards.py --no-stats          # skip the stats, keep old ones
    python scripts/generate_cards.py --force-stats       # recompute every dataset's stats
    python scripts/generate_cards.py --dataset tonas --local   # stats from ~/mir_datasets/tonas
"""

import argparse
import os
import tempfile

import mirdata

import card_fields
import cards_io
import hashes
import llm
from stats import to_card
from stats import dataset as stats_dataset
from stats.common import add_stats_arguments, print_to_do, select_datasets


def build_card(ds, summarize=True, stats=None):
    """The card dict for one initialized dataset; keys in card order.

    stats is the card's stats field, decided by card_stats() (computed,
    kept from the old card, or None).
    """
    return {
        "name": ds.name,
        "license": card_fields.license(ds),
        "annotations": card_fields.annotations(ds),
        "bibtex": card_fields.bibtex(ds),
        "summary": llm.summary(ds) if summarize else None,
        "stats": stats,
    }


def card_stats(ds, old, options):
    """(stats field, "new" or "kept" or "none") for one dataset.

    options: None to keep the old stats as they are (--no-stats), else a dict
    with local, datasets_dir, fetch_root, max_mb, max_minutes, force.
    """
    if options is None:
        return old, "kept" if old else "none"
    if options["local"] and not os.path.isdir(os.path.join(options["datasets_dir"], ds.name)):
        return old, "kept (no local copy)" if old else "none (no local copy)"
    fingerprint = to_card.index_fingerprint(ds)
    if not to_card.needs_compute(old, fingerprint, options["force"], options["local"]):
        return old, "kept"
    root = options["datasets_dir"] if options["local"] else options["fetch_root"]
    result = stats_dataset.compute(
        ds.name,
        os.path.join(root, ds.name),
        local=options["local"],
        max_mb=options["max_mb"],
        max_minutes=options["max_minutes"],
    )
    mode = "local" if options["local"] else "remote"
    new = to_card.card_stats(result, mode, fingerprint)
    chosen = to_card.choose(old, new, fingerprint)
    return chosen, "new" if chosen is new else "kept (more complete than the new run)"


def generate(names, output_dir, summarize=True, force=False, stats_options=None):
    """Write a card for each dataset name. Returns (written, skipped).

    The LLM runs only for datasets whose docstring hash is new or changed
    (or for all of them with force=True). With summarize=False it never runs
    and each card keeps the summary it already has (or gets null).
    stats_options: see card_stats(); None keeps every card's stats as they are.
    """
    os.makedirs(output_dir, exist_ok=True)
    stored = hashes.read(output_dir)
    updated = dict(stored)
    written = []
    skipped = {}
    card_stats_by_name = {}  # name -> the card's stats, for the closing to-do list

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
            stats, stats_status = card_stats(ds, old.get("stats"), stats_options)
            card = build_card(ds, summarize=redo, stats=stats)
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
            f" | summary: {status} | stats: {stats_status}, {to_card.status_line(stats)}"
        )
        card_stats_by_name[name] = stats

    if updated != stored:
        hashes.write(output_dir, updated)
    print(f"\nDone. Written: {len(written)}, skipped: {len(skipped)}")
    print_to_do(card_stats_by_name, "python scripts/generate_cards.py --local --dataset <name>")
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
        "--no-stats",
        action="store_true",
        help="Skip the stats; cards keep the stats they already have",
    )
    parser.add_argument(
        "--force-stats",
        action="store_true",
        help="Recompute the stats even if the dataset index is unchanged",
    )
    add_stats_arguments(parser)
    parser.add_argument(
        "--init-hashes",
        action="store_true",
        help="Only record docstring hashes for cards that have a summary; no LLM",
    )
    args = parser.parse_args()

    names = select_datasets(mirdata.list_datasets(), args.dataset)
    if args.missing and not args.dataset:
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

    with tempfile.TemporaryDirectory(prefix="generate_cards_") as fetch_root:
        stats_options = None if args.no_stats else {
            "local": args.local,
            "datasets_dir": args.datasets_dir,
            "fetch_root": fetch_root,
            "max_mb": args.max_mb,
            "max_minutes": args.max_minutes,
            "force": args.force_stats,
        }
        generate(
            names,
            args.output,
            summarize=not args.no_summary,
            force=args.force,
            stats_options=stats_options,
        )


if __name__ == "__main__":
    main()
