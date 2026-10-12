"""Helpers shared by the audio and the annotation stats and their command lines."""

import argparse
import json
import os
import threading
import time

from mirdata import download_utils

DEFAULT_DATASETS_DIR = os.path.join(os.path.expanduser("~"), "mir_datasets")  # mirdata's default
MAX_REMOTE_MB = 500  # default budget per dataset and part: data read from the remotes
MAX_REMOTE_MINUTES = 10  # default budget per dataset and part: time spent reading remotes


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
        if self.max_minutes is not None and time.monotonic() - self.start > self.max_minutes * 60:
            raise RemoteLimit(f"took longer than the {self.max_minutes} min remote limit")
        if self.max_mb is not None and self.bytes + more_bytes > self.max_mb * 1e6:
            raise RemoteLimit(
                f"needs more than the {self.max_mb} MB remote limit "
                f"({(self.bytes + more_bytes) / 1e6:.1f} MB)"
            )

    def charge(self, n_bytes):
        with self._lock:
            self.bytes += n_bytes


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
