"""Audio stats of one dataset, counted from its index: tracks and audio files.

No audio file is read, remote or local. Durations and sample rates will come
from mirdata's index once it carries them.
"""

from stats.audio.summary import summarize


def dataset_stats(name, index):
    """Count the tracks and audio files of one dataset. Returns a dict.

    index: the dataset's index dict. The status is always ok: a local run
    would find nothing the index does not already say.
    """
    return {"name": name, "status": "ok", "problems": [], **summarize(index)}
