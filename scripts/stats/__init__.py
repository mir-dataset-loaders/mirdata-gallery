"""Dataset statistics for the gallery cards: audio (stats.audio) and annotations (stats.annotations).

compute() is the one place that runs both parts for one dataset. It
initializes the dataset with the folder its files are read from or fetched
into, then runs each part on its own: a part that fails holds
{"status": "error", "error": ...} and does not stop the other.
scripts/local/compute_stats_local.py prints the result, scripts/generate_cards.py
turns it into the card's stats field (stats/to_card.py).
"""

import functools
import json
import os
import time

import mirdata
from mirdata import download_utils

from stats import annotations, audio

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
    workers=4,
    verbose=False,
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

    index = functools.cache(lambda: load_index(ds))  # loaded once, by the first part that needs it
    for part in parts:
        t0 = time.time()
        try:
            if part == "audio":  # counted from the index, whatever the mode
                result[part] = audio.dataset_stats(index())
            else:  # a local run reads the files on disk: no index needed
                result[part] = annotations.dataset_stats(
                    ds,
                    data_home,
                    index=None if local else index(),
                    local=local,
                    workers=workers,
                    verbose=verbose,
                )
        except Exception as e:  # one broken part must not stop the other
            result[part] = {"status": "error", "error": f"{type(e).__name__}: {e}"}
        if on_part:
            on_part(part, result[part], time.time() - t0)
    return result
