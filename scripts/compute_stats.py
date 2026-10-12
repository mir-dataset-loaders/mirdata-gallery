"""Audio and annotation statistics of mirdata datasets, for the gallery cards.

For each dataset, two parts (see the stats package for what each computes):
  audio        track count, total duration, duration histogram, sample rates,
               read from the audio file headers (stats.audio)
  annotations  one entry per annotation property with histograms and label
               counts, from mirdata's own loaders (stats.annotations)

The result per dataset is {"name", "audio", "annotations"}; a part that fails
holds {"error": ...} and does not stop the other part or the other datasets.
Each part has a "status":
  ok           complete
  incomplete   some files could not be read, and a local copy would not help
               (a corrupt file, a loader bug); see its errors
  needs_local  the remotes cannot give a complete answer: no remotes
               (restricted or manual download), no access, archives that
               cannot be read remotely (tar.gz), files or a run over the
               remote limits; its "problems" say why. Run it with --local.
The run ends with the list of datasets to run locally.

Usage:
    python scripts/compute_stats.py --dataset rwc_popular                    # both parts
    python scripts/compute_stats.py --dataset rwc_popular --only audio
    python scripts/compute_stats.py --dataset rwc_popular --only annotations
    python scripts/compute_stats.py --dataset rwc_popular --limit 5          # quick look
    python scripts/compute_stats.py --dataset rwc_popular --json
    python scripts/compute_stats.py --exclude acousticbrainz_genre           # every other dataset
    python scripts/compute_stats.py --dataset rwc_popular --local            # ~/mir_datasets/<name>
    python scripts/compute_stats.py --local --datasets-dir /path/to/mir_datasets
    python scripts/compute_stats.py --dataset rwc_popular --fetch-dir /tmp/ann  # keep fetched files
    python scripts/compute_stats.py --max-mb 2000 --max-minutes 30           # larger remote limits

Two modes. By default everything comes from the dataset's remotes and the
audio is never downloaded: audio durations are read from the file headers by
HTTP range requests into the zip remotes, and the annotation and metadata
files the index lists are fetched into a temporary folder (or --fetch-dir).
Remote reading is limited per dataset and part to --max-mb megabytes and
--max-minutes minutes (default 500 MB, 10 min); past either, the part stops
and needs_local. With --local both parts read a local copy of the dataset
instead, without limits. Nothing is written; the result is printed.
"""

import argparse
import json
import os
import tempfile
import time

import mirdata

from stats import annotations, audio
from stats.common import (
    DEFAULT_DATASETS_DIR,
    MAX_REMOTE_MB,
    MAX_REMOTE_MINUTES,
    Budget,
    hms,
    load_index,
    positive_int,
    select_datasets,
)
from stats.histograms import format_histogram

PARTS = ("audio", "annotations")


# --------------------------------------------------------------- computing


def budget(args):
    """A fresh remote budget for one part of one dataset."""
    return Budget(args.max_mb, args.max_minutes)


def audio_part(name, ds, args, data_home):
    """stats.audio for one dataset, from its remotes or (--local) from data_home."""
    stats = audio.dataset_stats(
        name,
        load_index(ds),
        ds.remotes or {},
        args.workers,
        args.limit,
        args.verbose,
        data_home if args.local else None,
        budget=None if args.local else budget(args),
    )
    stats.pop("name", None)
    return stats


def annotations_part(name, ds, args, data_home):
    """stats.annotations for one dataset, fetched into data_home or (--local) read from it."""
    if args.local:
        stats = annotations.local_stats(name, data_home, args.limit, args.verbose)
    else:
        stats = annotations.remote_stats(
            name, ds, data_home, args.limit, args.workers, args.verbose, budget(args)
        )
    stats.pop("name", None)
    return stats


def compute(name, args, fetch_root):
    """{"name", "audio", "annotations"} for one dataset; printed as it goes unless --json."""
    if not args.json:
        print(name)
    data_home = os.path.join(args.datasets_dir if args.local else fetch_root, name)
    result = {"name": name}
    try:
        ds = mirdata.initialize(name, data_home=data_home)
    except Exception as e:  # a loader that cannot even be initialized
        result["error"] = f"{type(e).__name__}: {e}"
        if not args.json:
            print(f"  error: {result['error']}")
        return result
    for part in args.only:
        t0 = time.time()
        try:
            compute_part = audio_part if part == "audio" else annotations_part
            result[part] = compute_part(name, ds, args, data_home)
        except Exception as e:  # one broken part must not stop the other
            result[part] = {"status": "error", "error": f"{type(e).__name__}: {e}"}
        if not args.json:
            print_part(part, result[part], args.limit, time.time() - t0)
    return result


# ---------------------------------------------------------------- printing


def fmt(value):
    """One short string for a histogram, a label dict, or a scalar."""
    if value is None:
        return "-"
    if isinstance(value, dict):
        if set(value) == {"unit", "edges", "counts"}:
            return format_histogram(value)
        return ", ".join(f"{k}: {v}" for k, v in value.items())
    return str(value)


def print_part(part, stats, limit, elapsed):
    print(f"  [{part}]")
    if "error" in stats:
        print(f"  error: {stats['error']}")
        return
    (print_audio if part == "audio" else print_annotations)(stats, limit)
    print(f"  status:                 {stats['status']}")
    for problem in stats["problems"]:
        print(f"    {problem}")
    print(f"  elapsed:                {elapsed:.1f} s")


def print_to_do(results):
    """The datasets whose parts need a local run, and those left incomplete or failing."""
    groups = {"needs_local": [], "incomplete": [], "error": []}
    for name, result in results.items():
        if result.get("error"):
            groups["error"].append((name, "", result["error"]))
        for part in PARTS:
            stats = result.get(part)
            if stats and stats.get("status") in groups:
                why = (stats.get("problems") or [stats.get("error") or "see its errors"])[0]
                groups[stats["status"]].append((name, part, why))
    titles = {
        "needs_local": "Run these locally (python scripts/compute_stats.py --local --dataset <name>):",
        "incomplete": "Incomplete (some files could not be read; a local run would not help):",
        "error": "Failed:",
    }
    for status, rows in groups.items():
        if rows:
            print(f"\n{titles[status]}")
            for name, part, why in rows:
                print(f"  {name:28s} {part:12s} {why[:110]}")


def print_audio(stats, limit):
    """The terminal block for one dataset's audio."""
    print("\n".join(stats["sources"]))
    print(f"  tracks in index:        {stats['n_tracks']}")
    print(f"  with audio in index:    {stats['n_tracks_with_audio']}")
    print(f"  counted from files:     {stats['n_tracks_counted']}")
    print(f"  total duration:         {stats['total_seconds']:.0f} s = {hms(stats['total_seconds'])}")
    if stats["duration_histogram"]:
        print(f"  durations:              {format_histogram(stats['duration_histogram'])}")
    if stats["sample_rate"]:
        print(f"  sample rate:            {stats['sample_rate']} Hz (all files)")
    elif stats["sample_rates"]:
        counts = ", ".join(f"{sr} Hz x {n}" for sr, n in stats["sample_rates"].items())
        print(f"  sample rates:           {counts}")
    if stats["n_audio_files"] != stats["n_tracks_with_audio"]:
        print(
            f"  all audio files:        {stats['n_audio_files_counted']}/{stats['n_audio_files']}"
            f" read, {hms(stats['all_files_seconds'])} in total"
        )
    if stats["errors"]:
        print(f"  errors:                 {len(stats['errors'])}")
        if stats["status"] != "needs_local":  # else they follow from the problems below
            for path, error in list(stats["errors"].items())[:5]:
                print(f"    {path}: {error}")
    if limit:
        print(f"  (only the first {limit} audio files were read)")


def print_annotations(stats, limit):
    """The terminal block for one dataset's annotations."""
    print("\n".join(stats.get("sources", [])))
    brief = stats["status"] == "needs_local"  # details follow from the problems below
    missing = stats.get("missing_files", {})
    if missing:
        print(f"  files not fetched:      {len(missing)}")
        for path, why in list(missing.items())[:0 if brief else 5]:
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
        print(f"  {prop} failed on {failed['n_tracks']} tracks" + ("" if brief else ", e.g."))
        for track_id, error in list(failed["examples"].items())[:0 if brief else 3]:
            print(f"    {track_id}: {error[:150]}")
    if stats["errors"]:
        print(f"  errors:                 {len(stats['errors'])}")
        for track_id, error in list(stats["errors"].items())[:0 if brief else 5]:
            print(f"    {track_id}: {error}")
    if limit:
        print(f"  (only the first {limit} tracks were read)")


def print_table(results):
    """One line per dataset, after a run over several datasets."""
    print(f"\n{'dataset':36s} {'tracks':>7s} {'counted':>10s}  {'duration':>13s}  {'rate':>6s}  {'annotations':>11s}")
    for name, result in results.items():
        a, n = result.get("audio") or {}, result.get("annotations") or {}
        ok_a = a and "error" not in a
        tracks = a.get("n_tracks", n.get("n_tracks", "-")) if not result.get("error") else "-"
        counted = f"{a['n_tracks_counted']}/{a['n_tracks_with_audio']}" if ok_a else "-"
        duration = hms(a["total_seconds"]) if ok_a and a["n_tracks_counted"] else "-"
        rate = str(a["sample_rate"]) if ok_a and a["sample_rate"] else ("mixed" if ok_a and a["sample_rates"] else "-")
        entries = str(len(n["annotations"])) if n and "error" not in n else "-"
        note = result.get("error") or a.get("error") or n.get("error") or ""
        print(f"{name:36s} {str(tracks):>7s} {counted:>10s}  {duration:>13s}  {rate:>6s}  {entries:>11s}  {note[:60]}")


# ------------------------------------------------------------ command line


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dataset", default=None, help="one dataset (default: every dataset)")
    parser.add_argument(
        "--exclude", default="", help="comma-separated datasets to skip, e.g. acousticbrainz_genre"
    )
    parser.add_argument(
        "--only", choices=PARTS, default=None, help="compute only the audio or only the annotations"
    )
    parser.add_argument(
        "--limit",
        type=positive_int,
        default=None,
        help="quick look: only the first N audio files (audio) and N tracks (annotations)",
    )
    parser.add_argument("--workers", type=int, default=4, help="parallel range requests")
    parser.add_argument("--verbose", action="store_true", help="print one line per file or track")
    parser.add_argument("--json", action="store_true", help="print the result as JSON")
    parser.add_argument(
        "--local", action="store_true", help="read local copies of the datasets, not the remotes"
    )
    parser.add_argument(
        "--datasets-dir",
        default=DEFAULT_DATASETS_DIR,
        help="with --local: folder with one sub-folder per dataset (default: ~/mir_datasets)",
    )
    parser.add_argument(
        "--max-mb",
        type=positive_int,
        default=MAX_REMOTE_MB,
        help=f"remote limit per dataset and part, in MB read (default {MAX_REMOTE_MB})",
    )
    parser.add_argument(
        "--max-minutes",
        type=positive_int,
        default=MAX_REMOTE_MINUTES,
        help=f"remote limit per dataset and part, in minutes (default {MAX_REMOTE_MINUTES})",
    )
    parser.add_argument(
        "--fetch-dir",
        default=None,
        help="keep the fetched annotation files in this folder (default: a temporary folder, deleted)",
    )
    args = parser.parse_args(argv)
    args.only = (args.only,) if args.only else PARTS
    return args


def main(argv=None):
    args = parse_args(argv)
    names = select_datasets(mirdata.list_datasets(), args.dataset, args.exclude)
    with tempfile.TemporaryDirectory(prefix="compute_stats_") as tmp:
        fetch_root = args.fetch_dir or tmp
        results = {name: compute(name, args, fetch_root) for name in names}
    if args.json:
        print(json.dumps(results, indent=2))
        return
    if len(names) > 1:
        print_table(results)
    print_to_do(results)


if __name__ == "__main__":
    main()
