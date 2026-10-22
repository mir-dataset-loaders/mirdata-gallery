"""Local tool: print the audio and annotation stats of mirdata datasets to inspect.

Shows everything, including the logs and per-file errors a card leaves out,
and writes nothing: generate_cards.py puts the stats into the cards. Each
part ends with a status: ok, incomplete, or needs_local (rerun with --local).

Usage:
    python scripts/local/compute_stats_local.py --dataset rwc_popular            # both parts
    python scripts/local/compute_stats_local.py --dataset rwc_popular --only audio
    python scripts/local/compute_stats_local.py --dataset rwc_popular --only annotations
    python scripts/local/compute_stats_local.py --dataset rwc_popular --limit 5  # quick look
    python scripts/local/compute_stats_local.py --dataset rwc_popular --json
    python scripts/local/compute_stats_local.py --exclude acousticbrainz_genre   # every other dataset
    python scripts/local/compute_stats_local.py --dataset rwc_popular --local    # ~/mir_datasets/<name>
    python scripts/local/compute_stats_local.py --local --datasets-dir /path/to/mir_datasets
    python scripts/local/compute_stats_local.py --dataset rwc_popular --fetch-dir /tmp/ann  # keep fetched files
"""

import argparse
import json
import os
import sys
import tempfile

import mirdata

# scripts/local/ -> scripts/, where the gallery code (card_utils, stats, llm) lives
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import card_utils
import stats
import stats.histograms

# --------------------------------------------------------------- computing


def compute(name, args, fetch_root):
    """{"name", "audio", "annotations"} for one dataset; printed as it goes unless --json."""
    if not args.json:
        print(name)
    result = stats.compute(
        name,
        os.path.join(args.datasets_dir if args.local else fetch_root, name),
        local=args.local,
        parts=args.only,
        limit=args.limit,
        workers=args.workers,
        verbose=args.verbose,
        on_part=(
            None
            if args.json
            else lambda part, part_stats, s: print_part(part, part_stats, args.limit, s)
        ),
    )
    if "error" in result and not args.json:
        print(f"  error: {result['error']}")
    return result


# ---------------------------------------------------------------- printing


def hms(seconds):
    """1h 02m 03s, for the duration column."""
    h, rest = divmod(int(round(seconds)), 3600)
    m, s = divmod(rest, 60)
    return f"{h}h {m:02d}m {s:02d}s"


def fmt(value):
    """One short string for a histogram, a label dict, or a scalar."""
    if value is None:
        return "-"
    if isinstance(value, dict):
        if set(value) == {"unit", "edges", "counts"}:
            return stats.histograms.format_histogram(value)
        return ", ".join(f"{k}: {v}" for k, v in value.items())
    return str(value)


def print_part(part, part_stats, limit, elapsed):
    print(f"  [{part}]")
    if "error" in part_stats:
        print(f"  error: {part_stats['error']}")
        return
    (print_audio if part == "audio" else print_annotations)(part_stats, limit)
    print(f"  status:                 {part_stats['status']}")
    for problem in part_stats["problems"]:
        print(f"    {problem}")
    print(f"  elapsed:                {elapsed:.1f} s")


def print_audio(part_stats, limit):
    """The terminal block for one dataset's audio, counted from its index (limit does not apply)."""
    print(f"  tracks in index:        {part_stats['n_tracks']}")
    print(f"  audio files in index:   {part_stats['n_audio_files']}")


def print_annotations(part_stats, limit):
    """The terminal block for one dataset's annotations."""
    print("\n".join(part_stats.get("sources", [])))
    brief = (
        part_stats["status"] == "needs_local"
    )  # details follow from the problems below
    missing = part_stats.get("missing_files", {})
    if missing:
        print(f"  files not fetched:      {len(missing)}")
        for path, why in list(missing.items())[: 0 if brief else 5]:
            print(f"    {path}: {why}")
    print(f"  tracks in index:        {part_stats['n_tracks']}")
    print(f"  tracks loaded:          {part_stats['n_tracks_loaded']}")
    if part_stats["tracks_with"]:
        print(f"  tracks with:            {fmt(part_stats['tracks_with'])}")
    for prop, result in part_stats["annotations"].items():
        counts = f"{result['n_tracks']} tracks"
        if result["n_annotations"] != result["n_tracks"]:
            counts += f", {result['n_annotations']} annotations"
        print(f"  {prop} ({result['type']}; {counts})")
        for key, value in result.items():
            if key not in ("type", "n_tracks", "n_annotations"):
                print(f"    {key:<26} {fmt(value)}")
    for prop, why in part_stats["skipped"].items():
        print(f"  skipped {prop}: {why}")
    for prop, failed in part_stats["annotation_errors"].items():
        print(
            f"  {prop} failed on {failed['n_tracks']} tracks"
            + ("" if brief else ", e.g.")
        )
        for track_id, error in list(failed["examples"].items())[: 0 if brief else 3]:
            print(f"    {track_id}: {error[:150]}")
    if part_stats["errors"]:
        print(f"  errors:                 {len(part_stats['errors'])}")
        for track_id, error in list(part_stats["errors"].items())[: 0 if brief else 5]:
            print(f"    {track_id}: {error}")
    if limit:
        print(f"  (only the first {limit} tracks were read)")


def print_table(results):
    """One line per dataset, after a run over several datasets."""
    print(
        f"\n{'dataset':36s} {'tracks':>7s} {'audio files':>11s}  {'duration':>13s}  {'rate':>6s}  {'annotations':>11s}"
    )
    for name, result in results.items():
        a, n = result.get("audio") or {}, result.get("annotations") or {}
        ok_a = a and "error" not in a
        tracks = (
            a.get("n_tracks", n.get("n_tracks", "-"))
            if not result.get("error")
            else "-"
        )
        files = str(a["n_audio_files"]) if ok_a else "-"
        duration = (
            hms(a["total_seconds"]) if a.get("total_seconds") else "-"
        )  # until the index has durations
        rate = (
            str(a["sample_rate"])
            if a.get("sample_rate")
            else ("mixed" if a.get("sample_rates") else "-")
        )
        entries = str(len(n["annotations"])) if n and "error" not in n else "-"
        note = result.get("error") or a.get("error") or n.get("error") or ""
        print(
            f"{name:36s} {str(tracks):>7s} {files:>11s}  {duration:>13s}  {rate:>6s}  {entries:>11s}  {note[:60]}"
        )


# ------------------------------------------------------------ command line


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--dataset", default=None, help="one dataset (default: every dataset)"
    )
    parser.add_argument(
        "--exclude",
        default="",
        help="comma-separated datasets to skip, e.g. acousticbrainz_genre",
    )
    parser.add_argument(
        "--only",
        choices=stats.PARTS,
        default=None,
        help="compute only the audio or only the annotations",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="quick look: only the first N tracks (annotations)",
    )
    parser.add_argument(
        "--workers", type=int, default=4, help="parallel range requests"
    )
    parser.add_argument(
        "--verbose", action="store_true", help="print one line per file or track"
    )
    parser.add_argument("--json", action="store_true", help="print the result as JSON")
    parser.add_argument(
        "--local",
        action="store_true",
        help="compute the stats from local copies of the datasets, not the remotes",
    )
    parser.add_argument(
        "--datasets-dir",
        default=card_utils.DEFAULT_DATASETS_DIR,
        help="with --local: folder with one sub-folder per dataset (default: ~/mir_datasets)",
    )
    parser.add_argument(
        "--fetch-dir",
        default=None,
        help="keep the fetched annotation files in this folder (default: a temporary folder, deleted)",
    )
    args = parser.parse_args(argv)
    args.only = (args.only,) if args.only else stats.PARTS
    return args


def main(argv=None):
    args = parse_args(argv)
    names = card_utils.select_datasets(
        mirdata.list_datasets(), args.dataset, args.exclude
    )
    with tempfile.TemporaryDirectory(prefix="compute_stats_local_") as tmp:
        fetch_root = args.fetch_dir or tmp
        results = {name: compute(name, args, fetch_root) for name in names}
    if args.json:
        print(json.dumps(results, indent=2))
        return
    if len(names) > 1:
        print_table(results)
    card_utils.print_to_do(
        results, "python scripts/local/compute_stats_local.py --local --dataset <name>"
    )


if __name__ == "__main__":
    main()
