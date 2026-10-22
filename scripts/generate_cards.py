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
    python scripts/generate_cards.py --output some/dir
    python scripts/generate_cards.py --no-stats          # skip the stats, keep old ones
    python scripts/generate_cards.py --force-stats       # recompute every dataset's stats
    python scripts/generate_cards.py --dataset tonas --local   # stats from ~/mir_datasets/tonas
"""

import argparse
import os
import tempfile

import mirdata

import card_builder
import card_utils
import llm
import stats
import stats.card
import stats.utils


def update_stats(ds, old, options):
    """(stats field, "new" or "kept" or "none") for one dataset.

    options: None to keep the old stats as they are (--no-stats), else a dict
    with local, datasets_dir, fetch_root, max_mb, max_minutes, force.
    """
    if options is None:
        return old, "kept" if old else "none"
    if options["local"] and not os.path.isdir(
        os.path.join(options["datasets_dir"], ds.name)
    ):
        return old, "kept (no local copy)" if old else "none (no local copy)"
    checksum = stats.card.index_checksum(ds)
    if not (options["force"] or options["local"]) and stats.card.is_current(
        old, checksum
    ):
        return (
            old,
            "kept",
        )  # computed from this same index, and no flag asks for a rerun
    root = options["datasets_dir"] if options["local"] else options["fetch_root"]
    result = stats.compute(
        ds.name,
        os.path.join(root, ds.name),
        local=options["local"],
        max_mb=options["max_mb"],
        max_minutes=options["max_minutes"],
    )
    mode = "local" if options["local"] else "remote"
    new = stats.card.result_to_card_stats(result, mode, checksum)
    chosen = stats.card.choose(old, new, checksum)
    return chosen, "new" if chosen is new else "kept (more complete than the new run)"


def update_summary(ds, old, stored_hash, summarize=True, force=False):
    """(summary, docstring hash, "new" or "kept" or "none") for one card.

    The LLM runs only when summaries are on and the loader has a docstring
    that is new or changed (or with force, or when the card has no summary
    yet); otherwise the old summary is kept. old is the old card's summary,
    stored_hash the hash recorded for it. The hash is None when the loader
    has no docstring.
    """
    docstring = llm.loader_docstring(ds.name)
    current = card_utils.docstring_hash(docstring) if docstring else None
    if summarize and docstring and (force or current != stored_hash or not old):
        return llm.summary(ds), current, "new"
    if docstring or not summarize:
        return old, stored_hash, "kept"
    return None, None, "none"  # the loader has no docstring (any more)


def generate(names, output_dir, summarize=True, force=False, stats_options=None):
    """Write a card for each dataset name. Returns (written, skipped).

    The LLM runs only for datasets whose docstring hash is new or changed
    (or for all of them with force=True). With summarize=False it never runs
    and each card keeps the summary it already has (or gets null).
    stats_options: see update_stats(); None keeps every card's stats as they are.
    """
    os.makedirs(output_dir, exist_ok=True)
    stored = card_utils.read_hashes(output_dir)
    updated = dict(stored)
    written = []
    skipped = {}
    card_stats_by_name = {}  # name -> the card's stats, for the closing to-do list

    print(f"Scanning {len(names)} dataset(s) in mirdata...")
    for name in names:
        path = card_utils.card_path(output_dir, name)
        old = card_utils.read_card(path) or {}
        try:
            ds = mirdata.initialize(name)
            # Stats first: if they fail, the LLM has not been run for nothing.
            stats_field, stats_status = update_stats(
                ds, old.get("stats"), stats_options
            )
            summary, summary_hash, summary_status = update_summary(
                ds, old.get("summary"), stored.get(name), summarize, force
            )
            card = card_builder.build_card(ds, summary=summary, stats=stats_field)
        except ModuleNotFoundError as e:
            missing = str(e).replace("No module named ", "").strip("'")
            skipped[name] = f"missing library: {missing}"
            print(f"  [SKIP]  {name:30s} | needs: {missing}")
            continue
        except Exception as e:
            skipped[name] = str(e)
            print(f"  [ERROR] {name:30s} | {e}")
            continue

        if summary_hash:
            updated[name] = summary_hash
        else:  # loader has no docstring: no hash to remember
            updated.pop(name, None)

        card_utils.write_card(path, card)
        written.append(name)
        print(
            f"  [OK]    {name:30s} | annotations: {len(card['annotations'])}"
            f" | summary: {summary_status} | stats: {stats_status}, {stats.card.status_line(stats_field)}"
        )
        card_stats_by_name[name] = stats_field

    if updated != stored:
        card_utils.write_hashes(output_dir, updated)
    print(f"\nDone. Written: {len(written)}, skipped: {len(skipped)}")
    stats.utils.print_to_do(
        card_stats_by_name, "python scripts/generate_cards.py --local --dataset <name>"
    )
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
    stats.utils.add_stats_arguments(parser)
    args = parser.parse_args()

    names = stats.utils.select_datasets(mirdata.list_datasets(), args.dataset)
    if args.missing and not args.dataset:
        names = [
            n for n in names if not os.path.exists(card_utils.card_path(args.output, n))
        ]
        if not names:
            print("Every mirdata dataset already has a card.")
            return
        print(f"Datasets without a card: {', '.join(names)}")

    with tempfile.TemporaryDirectory(prefix="generate_cards_") as fetch_root:
        stats_options = (
            None
            if args.no_stats
            else {
                "local": args.local,
                "datasets_dir": args.datasets_dir,
                "fetch_root": fetch_root,
                "max_mb": args.max_mb,
                "max_minutes": args.max_minutes,
                "force": args.force_stats,
            }
        )
        generate(
            names,
            args.output,
            summarize=not args.no_summary,
            force=args.force,
            stats_options=stats_options,
        )


if __name__ == "__main__":
    main()
