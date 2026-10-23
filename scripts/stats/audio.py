"""Audio stats of one dataset, counted from its index: tracks and audio files.

No audio file is read, remote or local. Durations and sample rates will come
from mirdata's index once it carries them.
"""


def track_audio_paths(index):
    """{track_id: [relative audio paths]} for every track, from keys containing 'audio'."""
    result = {}
    for track_id, files in index.get("tracks", {}).items():
        paths = [
            value[0]
            for key, value in files.items()
            if "audio" in key.lower() and isinstance(value, list) and value and value[0]
        ]
        if paths:
            result[track_id] = paths
    return result


def summarize(index):
    """The per-dataset counts: tracks in the index, and distinct audio files they list."""
    tracks = track_audio_paths(index)
    audio_information = index.get("audio_summary", {}) #for updated indexes
    result =  {
        "n_tracks": len(index.get("tracks", {})),
        "n_audio_files": len({p for paths in tracks.values() for p in paths}),
    }
    if audio_information:
        sec = audio_information.get("total_audio_duration_seconds")
        result.update({
            "total_audio_duration_seconds": sec,
            "sample_rate_counts": audio_information.get("sample_rate_counts", {}),
            "channel_counts": audio_information.get("channel_counts", {}),
        })
    return result
            



def dataset_stats(name, index):
    """Count the tracks and audio files of one dataset. Returns a dict.

    index: the dataset's index dict. The status is always ok: a local run
    would find nothing the index does not already say.
    """
    return {"name": name, "status": "ok", "problems": [], **summarize(index)}
