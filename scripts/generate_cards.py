"""Generate one YAML card per mirdata dataset.

Every run rebuilds the cheap fields (license, annotations, bibtex). The LLM
summary and the stats are recomputed only when needed: when the loader
docstring changed or the dataset index changed (both recorded in the card:
docstring_hash and stats.computed.index). Datasets whose stats need a local
run are listed at the end.

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

    old is the old card ({} if none); options see generate(). With stats
    False the old stats are kept as they are (--no-stats).
    """
    old_stats = old.get("stats")
    if not options["stats"]:
        return old_stats, "kept" if old_stats else "none"
    if options["local"] and not os.path.isdir(
        os.path.join(options["datasets_dir"], ds.name)
    ):
        status = "kept (no local copy)" if old_stats else "none (no local copy)"
        return old_stats, status
    checksum = stats.card.index_checksum(ds)
    if not (options["force_stats"] or options["local"]) and stats.card.is_current(
        old_stats, checksum
    ):
        return (
            old_stats,
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
    chosen = stats.card.choose(old_stats, new, checksum)
    return chosen, "new" if chosen is new else "kept (more complete than the new run)"


def update_summary(ds, old, options):
    """(summary, docstring hash, "new" or "kept" or "none") for one card.

    The LLM runs only when summaries are on and the loader has a docstring
    that is new or changed (or with force_summary, or when the card has no
    summary yet); otherwise the old summary and its hash are kept. old is the
    old card ({} if none), whose docstring_hash is the hash of the docstring
    its summary was made from; options see generate(). The hash is None when
    the loader has no docstring.
    """
    summarize = options["summary"]
    old_summary, stored_hash = old.get("summary"), old.get("docstring_hash")
    docstring = llm.loader_docstring(ds.name)
    current = card_utils.docstring_hash(docstring) if docstring else None
    if (
        summarize
        and docstring
        and (options["force_summary"] or current != stored_hash or not old_summary)
    ):
        return llm.summary(ds.name, docstring), current, "new"
    if docstring or not summarize:
        return old_summary, stored_hash, "kept"
    return None, None, "none"  # the loader has no docstring (any more)


def generate(names, output_dir, options):
    """Write a card for each dataset name. Returns (written, skipped).

    options is a dict with:
      summary, force_summary: the LLM runs only for datasets whose docstring
        hash is new or changed (or for all of them with force_summary). With
        summary False it never runs and each card keeps the summary it
        already has (or gets null).
      stats, force_stats, local, datasets_dir, fetch_root, max_mb,
        max_minutes: see update_stats(); stats False keeps every card's stats
        as they are.
    """
    os.makedirs(output_dir, exist_ok=True)
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
            stats_field, stats_status = update_stats(ds, old, options)
            summary, summary_hash, summary_status = update_summary(ds, old, options)
            card = card_builder.build_card(
                ds, summary=summary, docstring_hash=summary_hash, stats=stats_field
            )
        except ModuleNotFoundError as e:
            missing = str(e).replace("No module named ", "").strip("'")
            skipped[name] = f"missing library: {missing}"
            print(f"  [SKIP]  {name:30s} | needs: {missing}")
            continue
        except Exception as e:
            skipped[name] = str(e)
            print(f"  [ERROR] {name:30s} | {e}")
            continue

        card_utils.write_card(path, card)
        written.append(name)
        print(
            f"  [OK]    {name:30s} | annotations: {len(card['annotations'])}"
            f" | summary: {summary_status} | stats: {stats_status}, {stats.card.status_line(stats_field)}"
        )
        card_stats_by_name[name] = stats_field

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
        options = {
            "summary": not args.no_summary,
            "force_summary": args.force,
            "stats": not args.no_stats,
            "force_stats": args.force_stats,
            "local": args.local,
            "datasets_dir": args.datasets_dir,
            "fetch_root": fetch_root,
            "max_mb": args.max_mb,
            "max_minutes": args.max_minutes,
        }
        generate(names, args.output, options)


if __name__ == "__main__":
    main()
