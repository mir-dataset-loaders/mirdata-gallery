"""Which index entries are audio files, and the per-dataset numbers from what was read."""

from collections import Counter

from stats import histograms


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


def summarize(index, durations, rates, errors):
    """The per-dataset numbers, from the index and what was read per audio file.

    durations and rates map index audio paths to seconds and sample rate;
    errors maps the paths that could not be read to a message.
    """
    tracks = track_audio_paths(index)
    wanted = {p for paths in tracks.values() for p in paths}
    rate_counts = Counter(rates.values())

    # One number per track: its first audio file that we could read.
    per_track = {}
    for track_id, paths in tracks.items():
        for p in paths:
            if p in durations:
                per_track[track_id] = durations[p]
                break

    return {
        "n_tracks": len(index.get("tracks", {})),
        "n_tracks_with_audio": len(tracks),  # tracks whose index entry lists an audio file
        "n_tracks_counted": len(per_track),  # tracks whose audio file we actually read
        "total_seconds": round(sum(per_track.values()), 1),
        "duration_histogram": histograms.duration_histogram(per_track.values()),
        "n_audio_files": len(wanted),
        "n_audio_files_counted": len(durations),
        "all_files_seconds": round(sum(durations.values()), 1),
        # One value when every file agrees, else None and look at the counts.
        "sample_rate": next(iter(rate_counts)) if len(rate_counts) == 1 else None,
        "sample_rates": dict(rate_counts.most_common()),
        "errors": errors,
    }
