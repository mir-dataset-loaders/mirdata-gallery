"""Audio stats of one dataset, from its index: tracks, audio files, durations and sample rates.

No audio file is read, remote or local.
"""

from collections import Counter

from stats import annotation_types


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


def track_features(track_id, files):
    """One track's (seconds, sample rate), or None when the index has no audio features for it.

    A track has one duration and one sample rate, so its audio files must all agree exactly.
    """
    features = (files.get("audio_features") or {}).values()
    values = {(f["duration_seconds"], f["sample_rate"]) for f in features}
    if len(values) > 1:
        raise ValueError(
            f"the audio files of {track_id} disagree, (seconds, sample rate): {sorted(values)}"
        )
    return values.pop() if values else None


def sample_rate_label(rate):
    """A sample rate in kHz without extra zeros: 44100 is 44.1k, 48000 is 48k."""
    return f"{rate / 1000:g}k"


def dataset_stats(index):
    """The audio stats of one dataset. Returns a dict.

    index: the dataset's index dict. The status is ok when it can be read: a
    local run would find nothing the index does not already say. Raises
    ValueError when a track's audio files disagree.
    """
    tracks = index.get("tracks", {})
    paths = track_audio_paths(index).values()
    features = [track_features(track_id, files) for track_id, files in tracks.items()]
    features = [feature for feature in features if feature]
    seconds = [duration for duration, _ in features]
    rates = Counter(sample_rate_label(rate) for _, rate in features)
    return {
        "status": "ok",
        "problems": [],
        "n_tracks": len(tracks),
        "n_audio_files": len({path for track in paths for path in track}),
        "total_seconds": round(sum(seconds), 1) if seconds else None,
        "sample_rates": dict(rates.most_common()) if rates else None,
        "durations": annotation_types.grid(seconds, "s"),
    }
