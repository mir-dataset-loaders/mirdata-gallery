"""Both parts of the stats for one dataset: the one place that runs them.

compute() initializes the dataset with the folder its files are read from or
fetched into, then runs each part (audio, annotations) on its own: a part
that fails holds {"status": "error", "error": ...} and does not stop the
other. Remote parts get a fresh Budget each; local parts have no limits.
scripts/compute_stats.py prints the result, scripts/generate_cards.py turns
it into the card's stats field (stats/to_card.py).
"""

import os
import time

import mirdata

from stats import annotations, audio
from stats.common import MAX_REMOTE_MB, MAX_REMOTE_MINUTES, PARTS, Budget, load_index


def audio_part(name, ds, index, data_home, local, limit, workers, verbose, budget):
    """stats.audio for one dataset, from its remotes or (local) from data_home."""
    stats = audio.dataset_stats(
        name,
        index(),
        ds.remotes or {},
        workers,
        limit,
        verbose,
        data_home if local else None,
        budget=budget,
    )
    stats.pop("name", None)
    return stats


def annotations_part(name, ds, index, data_home, local, limit, workers, verbose, budget):
    """stats.annotations for one dataset, fetched into data_home or (local) read from it."""
    if local:  # reads the files on disk: no index needed
        stats = annotations.local_stats(name, ds, data_home, limit, verbose)
    else:
        stats = annotations.remote_stats(name, ds, data_home, index(), limit, workers, verbose, budget)
    stats.pop("name", None)
    return stats


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

    for part in parts:
        t0 = time.time()
        budget = None if local else Budget(max_mb, max_minutes)
        try:
            run = audio_part if part == "audio" else annotations_part
            result[part] = run(name, ds, index, data_home, local, limit, workers, verbose, budget)
        except Exception as e:  # one broken part must not stop the other
            result[part] = {"status": "error", "error": f"{type(e).__name__}: {e}"}
        if on_part:
            on_part(part, result[part], time.time() - t0)
    return result
