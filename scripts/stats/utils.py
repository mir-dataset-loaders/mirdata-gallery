"""What compute_stats.py and generate_cards.py share: the stats flags, the dataset choice, the to-do list."""

import argparse
import os

from stats import PARTS
from stats.remote import MAX_REMOTE_MB, MAX_REMOTE_MINUTES

DEFAULT_DATASETS_DIR = os.path.join(
    os.path.expanduser("~"), "mir_datasets"
)  # mirdata's default


def select_datasets(all_names, dataset=None, exclude=""):
    """The datasets to run: one (--dataset) or all, minus the comma-separated --exclude."""
    names = list(all_names)
    if dataset:
        if dataset not in names:
            raise SystemExit(f"Dataset '{dataset}' not found in mirdata.")
        names = [dataset]
    excluded = {n.strip() for n in exclude.split(",") if n.strip()}
    return [n for n in names if n not in excluded]


def print_to_do(results, command):
    """List the datasets whose parts need a local run, and those left incomplete or failing.

    results: {name: {"error"?, "audio"?, "annotations"?}}, each part with a
    "status" and "problems" (or "error"): a compute result or a card's stats
    field, which have the same shape. command: how to rerun one dataset
    locally, shown in the heading.
    """
    groups = {"needs_local": [], "incomplete": [], "error": []}
    for name, result in results.items():
        if not result:
            continue
        if result.get("error"):
            groups["error"].append((name, "", result["error"]))
        for part in PARTS:
            stats = result.get(part)
            if stats and stats.get("status") in groups:
                why = (
                    stats.get("problems") or [stats.get("error") or "see its errors"]
                )[0]
                groups[stats["status"]].append((name, part, why))
    titles = {
        "needs_local": f"Run these locally ({command}):",
        "incomplete": "Incomplete (some files could not be read; a local run would not help):",
        "error": "Failed:",
    }
    for status, rows in groups.items():
        if rows:
            print(f"\n{titles[status]}")
            for name, part, why in rows:
                print(f"  {name:28s} {part:12s} {why[:110]}")


def add_stats_arguments(parser):
    """The stats flags shared by compute_stats.py and generate_cards.py."""
    parser.add_argument(
        "--local",
        action="store_true",
        help="compute the stats from local copies of the datasets, not the remotes",
    )
    parser.add_argument(
        "--datasets-dir",
        default=DEFAULT_DATASETS_DIR,
        help="with --local: folder with one sub-folder per dataset (default: ~/mir_datasets)",
    )
    parser.add_argument(
        "--max-mb",
        type=positive_int,
        default=MAX_REMOTE_MB,
        help=f"remote limit per dataset, in MB of annotation files downloaded (default {MAX_REMOTE_MB})",
    )
    parser.add_argument(
        "--max-minutes",
        type=positive_int,
        default=MAX_REMOTE_MINUTES,
        help=f"remote limit per dataset, in minutes of reading annotation remotes (default {MAX_REMOTE_MINUTES})",
    )


def positive_int(text):
    """argparse type for --limit: 0 or a negative number would silently read nothing."""
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError(f"must be a positive integer, got {text}")
    return value
