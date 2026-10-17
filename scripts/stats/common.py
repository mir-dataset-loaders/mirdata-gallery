"""Helpers shared by the audio and the annotation stats and their command lines."""

import argparse
import json
import os
import threading
import time

from mirdata import download_utils

DEFAULT_DATASETS_DIR = os.path.join(
    os.path.expanduser("~"), "mir_datasets"
)  # mirdata's default
MAX_REMOTE_MB = (
    2000  # default budget per dataset: annotation data downloaded from the remotes
)
MAX_REMOTE_MINUTES = (
    10  # default budget per dataset: time spent reading the annotation remotes
)
PARTS = ("audio", "annotations")


class RemoteLimit(Exception):
    """The remote budget ran out: this part should be computed locally (--local)."""


class Budget:
    """How much a remote run may read (MB) and how long it may take (minutes).

    Every remote read calls check() with the bytes it is about to fetch, then
    charge() with what it got; check() raises RemoteLimit once either limit
    would be passed, so a big download is refused before it starts. None
    means no limit. Thread-safe: reads run in parallel.
    """

    def __init__(self, max_mb=None, max_minutes=None):
        self.max_mb = max_mb
        self.max_minutes = max_minutes
        self.start = time.monotonic()
        self.bytes = 0
        self._lock = threading.Lock()

    def check(self, more_bytes=0):
        if (
            self.max_minutes is not None
            and time.monotonic() - self.start > self.max_minutes * 60
        ):
            raise RemoteLimit(
                f"took longer than the {self.max_minutes} min remote limit"
            )
        if self.max_mb is not None and self.bytes + more_bytes > self.max_mb * 1e6:
            raise RemoteLimit(
                f"needs more than the {self.max_mb} MB remote limit "
                f"({(self.bytes + more_bytes) / 1e6:.1f} MB)"
            )

    def charge(self, n_bytes):
        with self._lock:
            self.bytes += n_bytes


def remote_problems(kind, limit_hit, unmatched, unreadable):
    """The closing problems of a remote read: the limit, or the files no readable remote held.

    kind: "annotation"; limit_hit: the RemoteLimit message or None;
    unmatched: wanted files found in no remote; unreadable: "remote: why" for
    remotes that could not be read. After the limit the unread remotes explain
    the unmatched files, so only the limit is reported.
    """
    if limit_hit:
        return [f"remote limit: {limit_hit}"]
    if unmatched:
        why = f"; not readable: {'; '.join(unreadable)}" if unreadable else ""
        return [f"{len(unmatched)} {kind} files not found in the readable remotes{why}"]
    return []


def part_status(problems, incomplete):
    """ok, incomplete (some files failed; a local run would not help) or needs_local."""
    if problems:
        return "needs_local"
    return "incomplete" if incomplete else "ok"


def load_index(ds):
    """The dataset's index dict, fetching the index file (and only that) if needed."""
    if not os.path.exists(ds.index_path):
        # Never call ds.download(): some loaders override it and pull the whole dataset.
        path = download_utils.download_from_remote(
            ds._index_data.remote, ds._index_data.indexes_dir, False, False
        )
        with open(path, "rb") as f:
            if f.read(2) == b"PK":  # a few indexes are shipped zipped
                download_utils.unzip(path, cleanup=False)
    with open(ds.index_path, encoding="utf-8") as f:
        return json.load(f)


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


def hms(seconds):
    h, rest = divmod(int(round(seconds)), 3600)
    m, s = divmod(rest, 60)
    return f"{h}h {m:02d}m {s:02d}s"
