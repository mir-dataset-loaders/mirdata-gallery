"""Which index entries are audio files, and the per-dataset counts."""


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
    return {
        "n_tracks": len(index.get("tracks", {})),
        "n_audio_files": len({p for paths in tracks.values() for p in paths}),
    }
