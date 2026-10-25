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


def error_text(e):
    """An exception as one line: "ValueError: bad line"."""
    return f"{type(e).__name__}: {e}"


def read_tracks(ds, verbose=False):
    """Load every track of an initialized dataset and summarize its annotations."""
    # the same detection as the card's annotations field, official types only
    properties = {
        prop: ann_type
        for prop, ann_type in card_builder.annotation_properties(ds).items()
        if ann_type in ANNOTATION_TYPES
    }
    # typed by their return hint: a value of another type is an error, not a wrong guess
    declared = card_builder.annotation_properties(ds, guess=False)
    track_ids = ds.track_ids
    stats = {prop: STATS[ann_type]() for prop, ann_type in properties.items()}
    # annotation type -> ids of tracks with at least one such annotation
    tracks_with = {}
    skipped = {}  # guessed property -> why its values could not be used
    # track_id -> error while creating the track (none of its annotations read)
    errors = {}
    annotation_errors = {}  # property -> {track_id: error} while loading or reading it

    for track_id in track_ids:
        try:
            with quiet_logging():
                track = ds.track(track_id)
        except Exception as e:
            errors[track_id] = error_text(e)
            if verbose:
                print(f"    {track_id}: {errors[track_id]}", file=sys.stderr)
            continue
        for prop, ann_type in properties.items():
            # One property at a time: a broken annotation file costs only that annotation.
            try:
                with quiet_logging():
                    value = getattr(track, prop)
                if is_empty(value):
                    continue
                used = stats[prop].add(value)
            except Exception as e:
                annotation_errors.setdefault(prop, {})[track_id] = error_text(e)
                if verbose:
                    print(f"    {track_id} {prop}: {error_text(e)}", file=sys.stderr)
                continue
            if used:
                tracks_with.setdefault(ann_type, set()).add(track_id)
                continue
            why = f"not a mirdata {ann_type} object (got {type(value).__name__})"
            if prop in declared:
                annotation_errors.setdefault(prop, {})[track_id] = why
            else:
                skipped[prop] = why
        if verbose:
            print(f"    {track_id}: ok", file=sys.stderr)

    annotations = {
        prop: {"type": properties[prop], **stat.summary(), **stat.result()}
        for prop, stat in sorted(stats.items())
        if stat.n_tracks
    }
    return {
        "n_tracks": len(track_ids),
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


def dataset_stats(
    ds,
    data_home,
    index=None,
    local=False,
    workers=4,
    verbose=False,
    max_mb=remote.MAX_REMOTE_MB,
    max_minutes=remote.MAX_REMOTE_MINUTES,
):
    """Annotation stats of one dataset, read from a local copy (local=True) or fetched from its remotes.

    ds is initialized with data_home: the local copy (stats.compute checks it
    exists), or the folder the annotation files are fetched into. A remote run
    needs index (stats.load_index) and reads at most max_mb in max_minutes.
    The result carries "status" (ok, incomplete or needs_local), "problems"
    (why a local run is needed), "sources" (one line per remote, or the local
    folder) and "missing_files" ({path: why it was not fetched}).
    """
    if local:
        problems, sources, missing = [], [f"  local                  {data_home}"], {}
    else:
        _, missing, sources, problems = remote.fetch(
            ds.remotes,
            remote.annotation_paths(index),
            data_home,
            workers=workers,
            verbose=verbose,
            budget=remote.Budget(max_mb, max_minutes),  # one for the whole dataset
        )
        sources = index_notes(index) + sources
    stats = read_tracks(ds, verbose)
    incomplete = bool(missing or stats["errors"] or stats["annotation_errors"])
    return {
        **stats,
        "status": part_status(problems, incomplete),
        "problems": problems,
        "sources": sources,
        "missing_files": missing,
    }
