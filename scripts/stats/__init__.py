"""Dataset statistics for the gallery cards: audio (stats.audio) and annotations (stats.annotations).

compute() is the one place that runs both parts for one dataset. It
initializes the dataset with the folder its files are read from or fetched
into, then runs each part on its own: a part that fails holds
{"status": "error", "error": ...} and does not stop the other. A remote run
gets one Budget for the whole dataset, spent by the annotation downloads (the
audio part reads only the index). Local runs have no limits.
scripts/local/compute_stats_local.py prints the result, scripts/generate_cards.py
turns it into the card's stats field (stats/to_card.py).
"""

import json
import os
import time

import mirdata
from mirdata import download_utils

from stats import annotations, audio
from stats.remote import MAX_REMOTE_MB, MAX_REMOTE_MINUTES, Budget

PARTS = ("audio", "annotations")


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


def compute(
    name,
    data_home,
    local=False,
    parts=PARTS,
    limit=None,
    workers=4,
    verbose=False,
    max_mb=MAX_REMOTE_MB,
    max_minutes=MAX_REMOTE_MINUTES,
    on_part=None,
):
    """{"name", "audio", "annotations"} for one dataset.

    data_home: the local copy (local=True) or the folder remote annotation
    files are fetched into. parts: which parts to run. on_part(part, result,
    seconds) is called after each part, for printing as it goes. A loader
    that cannot be initialized, or (local) a missing local copy, gives
    {"name", "error"}.
    """
    result = {"name": name}
    if local and not os.path.isdir(data_home):
        result["error"] = f"no local copy at {data_home}"
        return result
    try:
        ds = mirdata.initialize(name, data_home=data_home)
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
        return result

    loaded = {}

    def index():
        """The dataset index, loaded once and shared by both parts (or its error, raised again)."""
        if "index" not in loaded:
            try:
                loaded["index"] = load_index(ds)
            except Exception as e:
                loaded["index"] = e
        if isinstance(loaded["index"], Exception):
            raise loaded["index"]
        return loaded["index"]

    budget = None if local else Budget(max_mb, max_minutes)  # one for the whole dataset
    for part in parts:
        t0 = time.time()
        try:
            if part == "audio":  # counted from the index, whatever the mode or limit
                part_stats = audio.dataset_stats(name, index())
            elif local:  # reads the files on disk: no index needed
                part_stats = annotations.local_stats(
                    name, ds, data_home, limit, verbose
                )
            else:
                part_stats = annotations.remote_stats(
                    name, ds, data_home, index(), limit, workers, verbose, budget
                )
            part_stats.pop("name", None)
            result[part] = part_stats
        except Exception as e:  # one broken part must not stop the other
            result[part] = {"status": "error", "error": f"{type(e).__name__}: {e}"}
        if on_part:
            on_part(part, result[part], time.time() - t0)
    return result
