"""The card's "stats" field, made from a computed result, and when to replace it.

A card keeps the numbers, histograms, statuses and problems, with error
counts instead of error lists. Its "computed" block records the mode and the
index checksum, so a later run knows whether the stats are still current.
"""

MODES = ("remote", "local")

# Keys copied from each part's result; everything else (log lines, per-file
# dicts) stays out of the card.
AUDIO_KEYS = ("status", "problems", "n_tracks", "n_audio_files","total_audio_duration_minutes",
    "sample_rate_counts",
    "channel_counts")
ANNOTATION_KEYS = (
    "status",
    "problems",
    "n_tracks",
    "n_tracks_loaded",
    "tracks_with",
    "annotations",
    "skipped",
)


def index_checksum(ds):
    """The MD5 checksum mirdata publishes with a dataset's index, without downloading it.

    A new index version comes with a new checksum, so it changes exactly when
    the index does.
    """
    return ds._index_data.remote.checksum


def audio_to_card(part):
    """The audio part as stored in a card."""
    if "error" in part:
        return {"status": "error", "error": part["error"]}
    return {key: part[key] for key in AUDIO_KEYS if key in part}


def annotations_to_card(part):
    """The annotations part as stored in a card: per-file and per-track details become counts."""
    if "error" in part:
        return {"status": "error", "error": part["error"]}
    card = {key: part[key] for key in ANNOTATION_KEYS if key in part}
    card["annotations"] = {
        prop: {
            # meter (beats per bar) and polyphony (pitches at once) are keyed by
            # numbers (4, 3, ...): numbers, even after a JSON round trip
            key: (
                {int(k): v for k, v in value.items()}
                if key in ("meter", "polyphony")
                else value
            )
            for key, value in entry.items()
        }
        for prop, entry in card.get("annotations", {}).items()
    }
    card["n_missing_files"] = len(part.get("missing_files", {}))
    card["n_track_errors"] = len(part.get("errors", {}))
    card["annotation_errors"] = {
        prop: failed["n_tracks"]
        for prop, failed in part.get("annotation_errors", {}).items()
    }
    return card


def result_to_card_stats(result, mode, checksum):
    """The "stats" field for one compute_stats result ({"name", "audio", "annotations"}).

    mode: "remote" or "local"; checksum: index_checksum of the dataset.
    """
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
    stats = {"computed": {"mode": mode, "index": checksum}}
    if "error" in result:  # the loader could not even be initialized
        stats["error"] = result["error"]
        return stats
    if "audio" in result:
        stats["audio"] = audio_to_card(result["audio"])
    if "annotations" in result:
        stats["annotations"] = annotations_to_card(result["annotations"])
    return stats


# ------------------------------------------------- keeping or replacing stats

STATUS_RANK = {"error": 0, "needs_local": 1, "incomplete": 2, "ok": 3}


def rank(stats):
    """How complete a stats field is: the rank of its worst part (-1 for none)."""
    if not stats:
        return -1
    if "error" in stats:
        return STATUS_RANK["error"]
    parts = [stats[part] for part in ("audio", "annotations") if part in stats]
    if not parts:
        return STATUS_RANK["error"]
    return min(STATUS_RANK.get(part.get("status"), 0) for part in parts)


def is_current(stats, checksum):
    """True when the stats were computed from this exact index."""
    return bool(stats) and (stats.get("computed") or {}).get("index") == checksum


def choose(old, new, checksum):
    """The stats to keep: the new ones, unless the old ones are current and more complete.

    So a local "ok" is never replaced by a later remote "needs_local" for the
    same index; a new index always takes the new stats.
    """
    if is_current(old, checksum) and rank(old) > rank(new):
        return old
    return new


def status_line(stats):
    """A short summary for the terminal: "audio ok, annotations needs_local"."""
    if not stats:
        return "none"
    if "error" in stats:
        return f"error ({stats['error'][:60]})"
    return ", ".join(
        f"{part} {stats[part]['status']}"
        for part in ("audio", "annotations")
        if part in stats
    )
