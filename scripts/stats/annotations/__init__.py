"""Distributions of the annotations of one mirdata dataset, from its remotes or a local copy.

The dataset's Track class tells which annotation types it exposes (the same
detection generate_cards.py uses for the card's "annotations" list). Every
track is loaded, and each of its annotation properties (beats,
leadsheet_chords, ...) is loaded on its own, so a broken annotation file
costs only that annotation and is logged under annotation_errors. Each
property is handed to its own Stat object for the property's type
(stats/annotations/types.py), which reduces it to a few numbers or labels; at the
end each Stat turns what it collected into histograms (see stats/histograms.py)
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

Remote mode: fetch.py pulls the annotation and metadata files the index
lists out of the dataset's remotes into a folder laid out like a local copy;
local mode reads a local copy. discovery.py finds the annotation properties.
"""

import logging
import os
import sys

import mirdata

from stats.annotations import fetch
from stats.annotations.discovery import annotation_properties
from stats.annotations.types import STATS, is_empty
from stats.common import load_index, part_status


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


def remote_stats(name, ds, data_home, limit=None, workers=4, verbose=False, budget=None):
    """Fetch the dataset's annotation files from its remotes into data_home, then dataset_stats.

    ds must be initialized with that data_home; budget is a stats.common.Budget
    for the remote reads. The result carries "status" (ok, incomplete or
    needs_local), "problems" (why a local run is needed), "sources" (one line
    per remote) and "missing_files" ({path: why it was not fetched}).
    """
    index = load_index(ds)
    track_ids = ds.track_ids[:limit] if limit else None
    wanted = fetch.annotation_paths(index, track_ids)
    _, missing, sources, problems = fetch.fetch(
        ds.remotes or {}, wanted, data_home, workers=workers, verbose=verbose, budget=budget
    )
    stats = dataset_stats(name, ds, limit, verbose)
    incomplete = bool(missing or stats["errors"] or stats["annotation_errors"])
    return {
        **stats,
        "status": part_status(problems, incomplete),
        "problems": problems,
        "sources": fetch.index_notes(index) + sources,
        "missing_files": missing,
    }


def local_stats(name, data_home, limit=None, verbose=False):
    """dataset_stats on a local copy of the dataset in data_home."""
    if not os.path.isdir(data_home):
        raise FileNotFoundError(f"no local copy at {data_home}")
    ds = mirdata.initialize(name, data_home=data_home)
    stats = dataset_stats(name, ds, limit, verbose)
    incomplete = bool(stats["errors"] or stats["annotation_errors"])
    return {
        **stats,
        "status": part_status([], incomplete),
        "problems": [],
        "sources": [f"  local                  {data_home}"],
        "missing_files": {},
    }
