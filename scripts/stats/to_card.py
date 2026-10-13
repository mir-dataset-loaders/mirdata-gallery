"""The card's "stats" field, made from a computed result, and when to replace it.

A card keeps the numbers, histograms, statuses and problems, with error
counts instead of error lists. Its "computed" block records the mode, the
index fingerprint and the date, so a later run knows whether the stats are
still current.
"""

import datetime
import hashlib

MODES = ("remote", "local")

# Keys copied from each part's result; everything else (log lines, per-file
# dicts) stays out of the card.
AUDIO_KEYS = (
    "status",
    "problems",
    "n_tracks",
    "n_tracks_with_audio",
    "n_tracks_counted",
    "total_seconds",
    "duration_histogram",
    "sample_rate",
    "sample_rates",
    "n_audio_files",
    "n_audio_files_counted",
    "all_files_seconds",
)
ANNOTATION_KEYS = (
    "status",
    "problems",
    "n_tracks",
    "n_tracks_loaded",
    "tracks_with",
    "annotations",
    "skipped",
)


def index_fingerprint(ds):
    """A short fingerprint of a dataset's index, without downloading it.

    mirdata publishes every index with its MD5 checksum, and a new index
    version comes with a new checksum, so the fingerprint changes exactly when
    the index does. An index without a remote (mirdata's test indexes) is
    hashed from its file instead.
    """
    remote = getattr(ds._index_data, "remote", None)
    if remote is not None and remote.checksum:
        return remote.checksum[:16]
    with open(ds.index_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()[:16]


def _number_keys(counts, kind=int):
    """{44100: 3} whether the keys arrive as numbers or (after JSON) as strings."""
    return {kind(k): v for k, v in counts.items()}


# Annotation fields whose keys are numbers (meter), not labels.
NUMBER_KEYED = {"beats_per_bar": int}


def _error_part(part):
    return {"status": "error", "error": part["error"]}


def audio_card(part):
    """The audio part as stored in a card."""
    if "error" in part:
        return _error_part(part)
    card = {key: part[key] for key in AUDIO_KEYS if key in part}
    if "sample_rates" in card:
        card["sample_rates"] = _number_keys(card["sample_rates"])
    card["n_errors"] = len(part.get("errors", {}))
    return card


def annotations_card(part):
    """The annotations part as stored in a card: per-file and per-track details become counts."""
    if "error" in part:
        return _error_part(part)
    card = {key: part[key] for key in ANNOTATION_KEYS if key in part}
    card["annotations"] = {
        prop: {
            key: _number_keys(value, NUMBER_KEYED[key]) if key in NUMBER_KEYED else value
            for key, value in entry.items()
        }
        for prop, entry in card.get("annotations", {}).items()
    }
    card["n_missing_files"] = len(part.get("missing_files", {}))
    card["n_track_errors"] = len(part.get("errors", {}))
    card["annotation_errors"] = {
        prop: failed["n_tracks"] for prop, failed in part.get("annotation_errors", {}).items()
    }
    return card


def card_stats(result, mode, fingerprint, date=None):
    """The "stats" field for one compute_stats result ({"name", "audio", "annotations"}).

    mode: "remote" or "local"; fingerprint: index_fingerprint of the dataset
    index; date: an ISO date string, today (UTC) by default.
    """
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
    date = date or datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    stats = {"computed": {"mode": mode, "index": fingerprint, "date": date}}
    if "error" in result:  # the loader could not even be initialized
        stats["error"] = result["error"]
        return stats
    if "audio" in result:
        stats["audio"] = audio_card(result["audio"])
    if "annotations" in result:
        stats["annotations"] = annotations_card(result["annotations"])
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


def is_current(stats, fingerprint):
    """True when the stats were computed from this exact index."""
    return bool(stats) and (stats.get("computed") or {}).get("index") == fingerprint


def needs_compute(old, fingerprint, force=False, local=False):
    """Whether to compute the stats again: none yet, a new index, or asked to (--force, --local)."""
    return force or local or not is_current(old, fingerprint)


def choose(old, new, fingerprint):
    """The stats to keep: the new ones, unless the old ones are current and more complete.

    So a local "ok" is never replaced by a later remote "needs_local" for the
    same index; a new index always takes the new stats.
    """
    if is_current(old, fingerprint) and rank(old) > rank(new):
        return old
    return new


def status_line(stats):
    """A short summary for the terminal: "audio ok, annotations needs_local"."""
    if not stats:
        return "none"
    if "error" in stats:
        return f"error ({stats['error'][:60]})"
    return ", ".join(f"{part} {stats[part]['status']}" for part in ("audio", "annotations") if part in stats)
