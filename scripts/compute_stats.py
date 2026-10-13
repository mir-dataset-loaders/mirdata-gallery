"""Print the audio and annotation stats of mirdata datasets, to inspect them.

Shows everything, including the logs and per-file errors a card leaves out,
and writes nothing: generate_cards.py puts the stats into the cards. Each
part ends with a status: ok, incomplete, or needs_local (rerun with --local).

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
"""

import argparse
import json
import os
import tempfile

import mirdata

from stats import dataset
from stats.common import PARTS, add_stats_arguments, hms, positive_int, print_to_do, select_datasets
from stats.histograms import format_histogram

# --------------------------------------------------------------- computing


def compute(name, args, fetch_root):
    """{"name", "audio", "annotations"} for one dataset; printed as it goes unless --json."""
    if not args.json:
        print(name)
    result = dataset.compute(
        name,
        os.path.join(args.datasets_dir if args.local else fetch_root, name),
        local=args.local,
        parts=args.only,
        limit=args.limit,
        workers=args.workers,
        verbose=args.verbose,
        max_mb=args.max_mb,
        max_minutes=args.max_minutes,
        on_part=None if args.json else lambda part, stats, s: print_part(part, stats, args.limit, s),
    )
    if "error" in result and not args.json:
        print(f"  error: {result['error']}")
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
    add_stats_arguments(parser)
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
    print_to_do(results, "python scripts/compute_stats.py --local --dataset <name>")


if __name__ == "__main__":
    main()
