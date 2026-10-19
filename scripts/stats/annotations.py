"""Annotation stats of one dataset: histograms and label counts per annotation property.

Only the ten official mirdata annotation types are read:
card_builder.annotation_properties finds them, annotation_types.py has one
Stat class per type. Each property of
each track is loaded on its own, so a broken file costs only that annotation.
In remote mode the files are first fetched into a folder (remote.py); in local
mode a local copy is read.
"""

import logging
import sys

import card_builder
from stats import remote
from stats.annotation_types import ANNOTATION_TYPES, STATS, is_empty


def part_status(problems, incomplete):
    """ok, incomplete (some files failed; a local run would not help) or needs_local."""
    if problems:
        return "needs_local"
    return "incomplete" if incomplete else "ok"


class quiet_logging:
    """Silence log records below ERROR (mirdata loaders warn per track) inside a with block."""

    def __enter__(self):
        logging.disable(logging.WARNING)

    def __exit__(self, *exc):
        logging.disable(logging.NOTSET)


def dataset_stats(name, ds, limit=None, verbose=False):
    """Load every track of an initialized dataset and summarize its annotations."""
    properties = (
        {  # the same detection as the card's annotations field, official types only
            prop: ann_type
            for prop, ann_type in card_builder.annotation_properties(ds).items()
            if ann_type in ANNOTATION_TYPES
        }
    )
    track_ids = ds.track_ids[:limit] if limit else ds.track_ids
    stats = {prop: STATS[ann_type]() for prop, ann_type in properties.items()}
    tracks_with = (
        {}
    )  # annotation type -> ids of tracks with at least one such annotation
    skipped = {}  # property -> why its values could not be used
    errors = (
        {}
    )  # track_id -> error while creating the track (none of its annotations read)
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
                skipped[prop] = (
                    f"not a mirdata {ann_type} object (got {type(value).__name__})"
                )
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
            prop: {
                "n_tracks": len(by_track),
                "examples": dict(list(by_track.items())[:3]),
            }
            for prop, by_track in sorted(annotation_errors.items())
        },
    }


def index_notes(index):
    """Log lines for index sections that are present but null (billboard's "metadata": null)."""
    return [
        f"  {'index':22s} \"{section}\" is null: no {section} files listed"
        for section in ("tracks", "multitracks", "metadata")
        if section in index and index[section] is None
    ]


def remote_stats(
    name, ds, data_home, index, limit=None, workers=4, verbose=False, budget=None
):
    """Fetch the dataset's annotation files from its remotes into data_home, then dataset_stats.

    ds must be initialized with that data_home; index is its index dict
    (stats.load_index); budget is a stats.remote.Budget for the remote
    reads. The result carries "status" (ok, incomplete or
    needs_local), "problems" (why a local run is needed), "sources" (one line
    per remote) and "missing_files" ({path: why it was not fetched}).
    """
    track_ids = ds.track_ids[:limit] if limit else None
    wanted = remote.annotation_paths(index, track_ids)
    _, missing, sources, problems = remote.fetch(
        ds.remotes or {},
        wanted,
        data_home,
        workers=workers,
        verbose=verbose,
        budget=budget,
    )
    stats = dataset_stats(name, ds, limit, verbose)
    incomplete = bool(missing or stats["errors"] or stats["annotation_errors"])
    return {
        **stats,
        "status": part_status(problems, incomplete),
        "problems": problems,
        "sources": index_notes(index) + sources,
        "missing_files": missing,
    }


def local_stats(name, ds, data_home, limit=None, verbose=False):
    """dataset_stats on a local copy of the dataset; ds is initialized with that data_home.

    stats.compute checks that the local copy exists.
    """
    stats = dataset_stats(name, ds, limit, verbose)
    incomplete = bool(stats["errors"] or stats["annotation_errors"])
    return {
        **stats,
        "status": part_status([], incomplete),
        "problems": [],
        "sources": [f"  local                  {data_home}"],
        "missing_files": {},
    }
