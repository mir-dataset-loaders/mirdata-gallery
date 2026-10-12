"""Distributions of the annotations of one mirdata dataset, from its remotes or a local copy.

The dataset's Track class tells which annotation types it exposes (the same
detection generate_cards.py uses for the card's "annotations" list). Every
track is loaded, and each of its annotation properties (beats,
leadsheet_chords, ...) is loaded on its own, so a broken annotation file
costs only that annotation and is logged under annotation_errors. Each
property is handed to its own Stat object for the property's type
(annotation_types.py), which reduces it to a few numbers or labels; at the
end each Stat turns what it collected into histograms (see histograms.py)
and label counts, as plain dicts ready for JSON or the card YAML. Only the ten official mirdata
annotation types are covered, and only the ones the dataset has show up;
nothing is written.

Only values that are instances of those classes are read; a property that
returns something else (a tempo string from the metadata, a MIDI object) is
reported as skipped. Results are keyed by property name, so a dataset with
two chord annotations gets two ChordData entries; "tracks_with" counts, per
type, the tracks that have at least one annotation of that type. Each beat
entry carries the tempo derived from it (60 / median inter-beat interval per
track); a TempoData property is an entry of its own.

mirdata's own log warnings (e.g. guitarset's note on solo chords) are
silenced while tracks are loaded.

Usage:
    python scripts/annotation_stats.py --dataset rwc_popular             # from the remotes
    python scripts/annotation_stats.py --dataset rwc_popular --limit 5   # first 5 tracks
    python scripts/annotation_stats.py --dataset rwc_popular --json
    python scripts/annotation_stats.py --dataset rwc_popular --fetch-dir /tmp/ann  # keep the files
    python scripts/annotation_stats.py --dataset rwc_popular --local     # from ~/mir_datasets/<name>
    python scripts/annotation_stats.py --local --datasets-dir /path/to/mir_datasets

Two modes, as in audio_stats.py. By default the annotation and metadata
files the index lists are pulled out of the dataset's zip remotes with
range requests (annotation_fetch.py), into a temporary folder or into
--fetch-dir, and the audio is never downloaded. With --local the files are
read from a local copy of the dataset instead, the way to go for datasets
without remotes or with archives that cannot be read by range.
"""

import argparse
import json
import logging
import os
import sys
import tempfile
import time

import mirdata

import annotation_fetch
from annotation_types import ANNOTATION_TYPES, STATS, is_empty
from audio_stats import load_index
from card_fields import _annotation_class_name
from histograms import format_histogram

DEFAULT_DATASETS_DIR = os.path.join(os.path.expanduser("~"), "mir_datasets")  # mirdata's default


# ---------------------------------------------------------------- discovery


def annotation_properties(ds):
    """{property name: annotation type} for the dataset's Track class.

    Uses the same detection as the card's "annotations" field, restricted to
    the official mirdata annotation types.
    """
    found = {}
    track_class = getattr(ds, "_track_class", None)
    for attr in dir(track_class):
        if attr.startswith("_"):
            continue
        item = getattr(track_class, attr, None)
        if isinstance(item, (property, mirdata.core.cached_property)):
            ann_cls = _annotation_class_name(attr, item)
            if ann_cls in ANNOTATION_TYPES:
                found[attr] = ann_cls
    return found


# ---------------------------------------------------------------- the stats


class quiet_logging:
    """Silence log records below ERROR (mirdata loaders warn per track) inside a with block."""

    def __enter__(self):
        logging.disable(logging.WARNING)

    def __exit__(self, *exc):
        logging.disable(logging.NOTSET)


def dataset_stats(name, ds, limit=None, verbose=False):
    """Load every track of an initialized dataset and summarize its annotations."""
    properties = annotation_properties(ds)
    track_ids = ds.track_ids[:limit] if limit else ds.track_ids
    stats = {prop: STATS[ann_type]() for prop, ann_type in properties.items()}
    tracks_with = {}  # annotation type -> ids of tracks with at least one such annotation
    skipped = {}  # property -> why its values could not be used
    errors = {}  # track_id -> error while creating the track (none of its annotations read)
    annotation_errors = {}  # property -> {track_id: error} while loading or reading it

    def annotation_error(prop, track_id, e):
        annotation_errors.setdefault(prop, {})[track_id] = f"{type(e).__name__}: {e}"
        if verbose:
            print(f"    {track_id} {prop}: {type(e).__name__}: {e}", file=sys.stderr)

    for track_id in track_ids:
        try:
            with quiet_logging():
                track = ds.track(track_id)
        except Exception as e:
            errors[track_id] = f"{type(e).__name__}: {e}"
            if verbose:
                print(f"    {track_id}: {errors[track_id]}", file=sys.stderr)
            continue
        for prop, ann_type in properties.items():
            # One property at a time: a broken annotation file costs only that annotation.
            try:
                with quiet_logging():
                    value = getattr(track, prop)
            except Exception as e:
                annotation_error(prop, track_id, e)
                continue
            if is_empty(value):
                continue
            try:
                used = stats[prop].add(value)
            except Exception as e:
                annotation_error(prop, track_id, e)
                continue
            if used:
                tracks_with.setdefault(ann_type, set()).add(track_id)
            else:
                skipped[prop] = f"not a mirdata {ann_type} object (got {type(value).__name__})"
        if verbose:
            print(f"    {track_id}: ok", file=sys.stderr)

    annotations = {
        prop: {"type": properties[prop], **stat.summary(), **stat.result()}
        for prop, stat in sorted(stats.items())
        if stat.n_tracks
    }
    return {
        "name": name,
        "n_tracks": len(ds.track_ids),
        "n_tracks_loaded": len(track_ids) - len(errors),
        "tracks_with": {t: len(ids) for t, ids in sorted(tracks_with.items())},
        "annotations": annotations,
        "skipped": skipped,
        "errors": errors,
        "annotation_errors": {
            prop: {"n_tracks": len(by_track), "examples": dict(list(by_track.items())[:3])}
            for prop, by_track in sorted(annotation_errors.items())
        },
    }


def remote_stats(name, ds, data_home, limit=None, workers=4, verbose=False):
    """Fetch the dataset's annotation files from its remotes into data_home, then dataset_stats.

    ds must be initialized with that data_home. The result carries "sources"
    (one line per remote) and "missing_files" ({path: why it was not fetched}).
    """
    index = load_index(ds)
    track_ids = ds.track_ids[:limit] if limit else None
    wanted = annotation_fetch.annotation_paths(index, track_ids)
    _, missing, sources = annotation_fetch.fetch(
        ds.remotes or {}, wanted, data_home, workers=workers, verbose=verbose
    )
    sources = annotation_fetch.index_notes(index) + sources
    stats = dataset_stats(name, ds, limit, verbose)
    return {**stats, "sources": sources, "missing_files": missing}


def local_stats(name, data_home, limit=None, verbose=False):
    """dataset_stats on a local copy of the dataset in data_home."""
    if not os.path.isdir(data_home):
        raise FileNotFoundError(f"no local copy at {data_home}")
    ds = mirdata.initialize(name, data_home=data_home)
    stats = dataset_stats(name, ds, limit, verbose)
    return {**stats, "sources": [f"  local                  {data_home}"], "missing_files": {}}


# --------------------------------------------------------------- command line


def fmt(value):
    """One short string for a histogram, a label dict, or a scalar."""
    if value is None:
        return "-"
    if isinstance(value, dict):
        if set(value) == {"unit", "edges", "counts"}:
            return format_histogram(value)
        return ", ".join(f"{k}: {v}" for k, v in value.items())
    return str(value)


def print_stats(stats, limit, elapsed):
    """The terminal block for one dataset."""
    print("\n".join(stats.get("sources", [])))
    missing = stats.get("missing_files", {})
    if missing:
        print(f"  files not fetched:      {len(missing)}")
        for path, why in list(missing.items())[:5]:
            print(f"    {path}: {why}")
    print(f"  tracks in index:        {stats['n_tracks']}")
    print(f"  tracks loaded:          {stats['n_tracks_loaded']}")
    if stats["tracks_with"]:
        print(f"  tracks with:            {fmt(stats['tracks_with'])}")
    for prop, result in stats["annotations"].items():
        counts = f"{result['n_tracks']} tracks"
        if result["n_annotations"] != result["n_tracks"]:
            counts += f", {result['n_annotations']} annotations"
        print(f"  {prop} ({result['type']}; {counts})")
        for key, value in result.items():
            if key not in ("type", "n_tracks", "n_annotations"):
                print(f"    {key:<26} {fmt(value)}")
    for prop, why in stats["skipped"].items():
        print(f"  skipped {prop}: {why}")
    for prop, failed in stats["annotation_errors"].items():
        print(f"  {prop} failed on {failed['n_tracks']} tracks, e.g.")
        for track_id, error in failed["examples"].items():
            print(f"    {track_id}: {error[:150]}")
    if stats["errors"]:
        print(f"  errors:                 {len(stats['errors'])}")
        for track_id, error in list(stats["errors"].items())[:5]:
            print(f"    {track_id}: {error}")
    if limit:
        print(f"  (only the first {limit} tracks were read)")
    print(f"  elapsed:                {elapsed:.1f} s")


def positive_int(text):
    """argparse type for --limit: 0 or a negative number would silently read nothing."""
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError(f"must be a positive integer, got {text}")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dataset", default=None, help="one dataset (default: every dataset)")
    parser.add_argument(
        "--exclude", default="", help="comma-separated datasets to skip, e.g. acousticbrainz_genre"
    )
    parser.add_argument(
        "--limit", type=positive_int, default=None, help="only read the first N tracks per dataset"
    )
    parser.add_argument("--verbose", action="store_true", help="print one line per track")
    parser.add_argument("--json", action="store_true", help="print the result as JSON")
    parser.add_argument("--workers", type=int, default=4, help="parallel range requests")
    parser.add_argument(
        "--fetch-dir",
        default=None,
        help="keep the fetched files in this folder (default: a temporary folder, deleted)",
    )
    parser.add_argument(
        "--local", action="store_true", help="read local copies of the datasets, not the remotes"
    )
    parser.add_argument(
        "--datasets-dir",
        default=DEFAULT_DATASETS_DIR,
        help="folder with one sub-folder per dataset (default: ~/mir_datasets)",
    )
    args = parser.parse_args()

    names = mirdata.list_datasets()
    if args.dataset:
        if args.dataset not in names:
            raise SystemExit(f"Dataset '{args.dataset}' not found in mirdata.")
        names = [args.dataset]
    excluded = {n.strip() for n in args.exclude.split(",") if n.strip()}
    names = [n for n in names if n not in excluded]

    with tempfile.TemporaryDirectory(prefix="annotation_stats_") as tmp:
        fetch_root = args.fetch_dir or tmp
        results = {name: run_one(name, args, fetch_root) for name in names}
    if args.json:
        print(json.dumps(results, indent=2))


def run_one(name, args, fetch_root):
    """Stats of one dataset in the mode the arguments ask for; printed unless --json."""
    t0 = time.time()
    if not args.json:
        print(name)
    try:
        if args.local:
            stats = local_stats(name, os.path.join(args.datasets_dir, name), args.limit, args.verbose)
        else:
            data_home = os.path.join(fetch_root, name)
            ds = mirdata.initialize(name, data_home=data_home)
            stats = remote_stats(name, ds, data_home, args.limit, args.workers, args.verbose)
    except Exception as e:  # one broken loader must not stop the others
        if not args.json:
            print(f"  error: {type(e).__name__}: {e}")
        return {"name": name, "error": f"{type(e).__name__}: {e}"}
    if not args.json:
        print_stats(stats, args.limit, time.time() - t0)
    return stats


if __name__ == "__main__":
    main()
