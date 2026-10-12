"""Track count and total audio duration of one mirdata dataset, without downloading it.

n_tracks is the number of entries in the dataset index. The duration is read
from the audio file headers: the dataset's zip archives are opened straight
from their URL with HTTP range requests (the server sends only the bytes we
ask for), so we fetch the zip's table of contents plus the first 64 KB of each
audio file and never write anything to disk. With a
data_home the same headers are read from a local copy instead.

The range reading lives in stats/remote_zip.py, the header parsers in
stats/audio/headers.py, the reading of local or remote files in
stats/audio/sources.py and the numbers in stats/audio/summary.py.
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
