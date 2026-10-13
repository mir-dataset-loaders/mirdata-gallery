"""Audio stats of one dataset: track count, durations and sample rates.

Durations come from the audio file headers only (headers.py), read by range
from the zip remotes or from a local copy (sources.py), then added up
(summary.py). No audio is decoded or downloaded whole.
"""

from stats.audio.sources import local_durations, remote_durations
from stats.audio.summary import summarize, track_audio_paths
from stats.common import part_status


def dataset_stats(name, index, remotes, workers=4, limit=None, verbose=False, data_home=None, budget=None):
    """Count tracks and read every audio duration of one dataset. Returns a dict.

    index: the dataset's index dict; remotes: its REMOTES dict (may be empty).
    data_home: when given, the audio is read from that local folder instead of
    the remotes (restricted or licensed audio). budget: a stats.common.Budget
    for the remote reads. The result carries "status" (ok, incomplete or
    needs_local) and "problems", the reasons a local run is needed.
    """
    tracks = track_audio_paths(index)
    wanted = {p for paths in tracks.values() for p in paths}
    if data_home is None:
        durations, rates, errors, sources, problems = remote_durations(
            remotes, wanted, workers, limit, verbose, budget
        )
    else:
        durations, rates, errors, sources, problems = local_durations(data_home, wanted, limit, verbose)
    return {
        "name": name,
        "status": part_status(problems, bool(errors)),
        "problems": problems,
        **summarize(index, durations, rates, errors),
        "sources": sources,
    }
