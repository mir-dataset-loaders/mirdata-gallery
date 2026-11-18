"""Annotation stats of one dataset: grid counts and label counts per annotation property.

Each name of each track is read on its own, so a broken file costs only that
annotation. In remote mode the files are first fetched into a folder
(remote.py); in local mode a local copy is read.
"""

import collections
import logging
import sys

import mirdata.core

from stats import annotation_types, remote


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


def drop_excluded_names(names):
    """Drop the names of a track that the stats never read.

    A name is dropped when it is private (starts with "_"), loads audio
    (contains "audio": reading it loads the whole audio file) or holds a
    file path (ends with "_path" or "_paths", as mirdata names every path).

    Args:
        names (iterable of str): names of a track's properties and attributes

    Returns:
        list of str: the names left, sorted

    """
    return sorted(
        name
        for name in names
        if not name.startswith("_")
        and "audio" not in name.lower()
        and not name.endswith(("_path", "_paths"))
    )


def collect_stats_candidates(track):
    """List the names of a track that the stats may read.

    The candidates are the properties of the track's class (plain and
    cached) and the attributes the track set when it was created, minus the
    names drop_excluded_names() removes.

    Args:
        track (mirdata.core.Track): a track of an initialized dataset

    Returns:
        list of str: the candidate names, sorted

    """
    track_class = type(track)
    properties = {
        name
        for name in dir(track_class)
        if isinstance(
            getattr(track_class, name, None),
            (property, mirdata.core.cached_property),
        )
    }
    return drop_excluded_names(properties | set(vars(track)))


def read_tracks(ds, verbose=False):
    """Load every track of an initialized dataset and summarize its annotations.

    Each candidate name gets its type from its first non-empty value
    (choose_stat); a name with no type is not read again. Errors from before
    a name had a type are held, then count as annotation errors, also when
    the name never gets a type. A value its Stat cannot use counts as a
    "WrongFormat" annotation error.

    Args:
        ds (mirdata.core.Dataset): an initialized dataset
        verbose (bool): print every track and error to stderr

    Returns:
        dict: the track counts, annotations, errors and annotation_errors

    """
    track_ids = ds.track_ids
    types = {}  # name -> annotation type, chosen from its first non-empty value
    stats = {}  # name -> the Stat that reads it
    dropped = set()  # names whose first non-empty value has no type: never read again
    held = {}  # name with no type yet -> {track_id: error} while reading it
    # annotation type -> ids of tracks with at least one such annotation
    tracks_with = {}
    # track_id -> error while creating the track (none of its annotations read)
    errors = {}
    annotation_errors = {}  # name -> {track_id: error or unusable value} while reading it

    for track_id in track_ids:
        try:
            with quiet_logging():
                track = ds.track(track_id)
        except Exception as e:
            errors[track_id] = error_text(e)
            if verbose:
                print(f"    {track_id}: {errors[track_id]}", file=sys.stderr)
            continue
        for name in collect_stats_candidates(track):
            if name in dropped:
                continue
            # One name at a time: a broken annotation file costs only that annotation.
            try:
                with quiet_logging():
                    value = getattr(track, name)
                if annotation_types.is_empty(value):
                    continue
                if name not in types:
                    ann_type = annotation_types.choose_stat(name, value)
                    if ann_type is None:
                        dropped.add(name)
                        held.pop(name, None)
                        continue
                    types[name] = ann_type
                    stats[name] = annotation_types.STATS[ann_type]()
                    if name in held:
                        annotation_errors[name] = held.pop(name)
                used = stats[name].add(value, track)
            except Exception as e:
                found = annotation_errors if name in types else held
                found.setdefault(name, {})[track_id] = error_text(e)
                if verbose:
                    print(f"    {track_id} {name}: {error_text(e)}", file=sys.stderr)
                continue
            if used:
                tracks_with.setdefault(types[name], set()).add(track_id)
                continue
            # "WrongFormat" stands in for an exception type, as in error_text()
            got = type(value).__name__
            why = (
                f"WrongFormat: no instrument labels (got {got})"
                if types[name] == "Instrument"
                else f"WrongFormat: not a mirdata {types[name]} object (got {got})"
            )
            annotation_errors.setdefault(name, {})[track_id] = why
        if verbose:
            print(f"    {track_id}: ok", file=sys.stderr)

    # names that raised on every track read, before they ever had a type
    annotation_errors.update(held)
    annotations = {
        name: {"type": types[name], **stat.summary(), **stat.result()}
        for name, stat in sorted(stats.items())
        if stat.n_tracks
    }
    return {
        "n_tracks": len(track_ids),
        "n_tracks_loaded": len(track_ids) - len(errors),
        "tracks_with": {t: len(ids) for t, ids in sorted(tracks_with.items())},
        "annotations": annotations,
        "errors": errors,
        "annotation_errors": {
            prop: {
                "n_tracks": len(by_track),
                # tracks with the same message become one entry, most common first
                "logs": [
                    {"error": error, "n_tracks": n}
                    for error, n in collections.Counter(by_track.values()).most_common()
                ],
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
    max_mb=remote.MAX_DOWNLOAD_MB,
):
    """Annotation stats of one dataset, read from a local copy (local=True) or fetched from its remotes.

    ds is initialized with data_home: the local copy (stats.compute checks it
    exists), or the folder the annotation files are fetched into. A remote run
    needs index (stats.load_index) and downloads at most max_mb.
    The result carries "status" (ok, incomplete or needs_local), "problems"
    (why a local run is needed), "sources" (one line per remote, or the local
    folder) and "missing_files" ({path: why it was not fetched}).
    """
    if local:
        problems, sources, missing = [], [f"  local                  {data_home}"], {}
    else:
        wanted, audio = remote.index_paths(index)
        _, missing, sources, problems = remote.fetch(
            ds.remotes,
            wanted,
            audio,
            data_home,
            workers=workers,
            verbose=verbose,
            budget=remote.Budget(max_mb),  # one for the whole dataset
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
