"""Track count and total audio duration of one mirdata dataset, without downloading it.

n_tracks is the number of entries in the dataset index. The duration is read
from the audio file headers: the dataset's zip archives are opened straight
from their URL with HTTP range requests (the server sends only the bytes we
ask for), so we fetch the zip's table of contents plus the first 64 KB of each
audio file and never write anything to disk.

Usage:
    python scripts/audio_stats.py                                  # every dataset
    python scripts/audio_stats.py --dataset rwc_popular            # just one
    python scripts/audio_stats.py --exclude acousticbrainz_genre   # skip some (334 MB index)
    python scripts/audio_stats.py --limit 5                        # quick look: 5 files per dataset
    python scripts/audio_stats.py --dataset rwc_popular --verbose  # one line per file
    python scripts/audio_stats.py --dataset rwc_popular --json
    python scripts/audio_stats.py --local                          # from ~/mir_datasets/<name>
    python scripts/audio_stats.py --local --datasets-dir /path/to/mir_datasets

Supported: zip remotes holding WAV, FLAC or MP3 files. Archives that cannot be
read by range (tar.gz, bz2) are reported and skipped for now. With --local the
same headers are read from local copies of the datasets instead of the remotes,
which is the way to go for restricted or licensed audio. Everything is printed
to the terminal; nothing is written.

The range reading lives in remote_zip.py and the header parsers in
audio_headers.py; this file matches index entries to files, adds up the
numbers and provides the command line.
"""

import argparse
import json
import os
import sys
import time
import zipfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import mirdata
import requests
from mirdata import download_utils

import audio_headers
import remote_zip

DEFAULT_DATASETS_DIR = os.path.join(os.path.expanduser("~"), "mir_datasets")  # mirdata's default


# ----------------------------------------------------------------------- index


def load_index(ds):
    """The dataset's index dict, fetching the index file (and only that) if needed."""
    if not os.path.exists(ds.index_path):
        # Never call ds.download(): some loaders override it and pull the whole dataset.
        path = download_utils.download_from_remote(
            ds._index_data.remote, ds._index_data.indexes_dir, False, False
        )
        with open(path, "rb") as f:
            if f.read(2) == b"PK":  # a few indexes are shipped zipped
                download_utils.unzip(path, cleanup=False)
    with open(ds.index_path, encoding="utf-8") as f:
        return json.load(f)


def track_audio_paths(index):
    """{track_id: [relative audio paths]} for every track, from keys containing 'audio'."""
    result = {}
    for track_id, files in index.get("tracks", {}).items():
        paths = [
            value[0]
            for key, value in files.items()
            if "audio" in key.lower() and isinstance(value, list) and value and value[0]
        ]
        if paths:
            result[track_id] = paths
    return result


# -------------------------------------------------------------------- reading


def record(results, durations, rates, errors, verbose):
    """Sort (path, (seconds, sample rate), error) triples into the result dicts."""
    for path, audio, error in results:
        if error:
            errors[path] = error
        else:
            durations[path], rates[path] = audio
        if verbose:
            line = f"{error}" if error else f"{audio[0]:10.2f} s  {audio[1]:6d} Hz"
            print(f"    {path:60s} {line}")


def remote_durations(remotes, wanted, workers, limit, verbose):
    """Durations read over range requests from the dataset's zip remotes.

    remotes: {key: RemoteFileMetadata}, as in a loader's REMOTES dict.
    """
    if not remotes:
        return {}, {}, {}, ["  (no remotes: the audio has to be obtained manually)"]
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=workers, pool_maxsize=workers)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    durations, rates, errors, sources = {}, {}, {}, []
    matched = set()  # every index path some remote contains, read or not
    for key, remote in remotes.items():
        if not remote.filename.lower().endswith(".zip"):
            sources.append(f"  {key:22s} {remote.filename}: not a zip, skipped")
            continue
        t0 = time.time()
        try:
            http = remote_zip.HTTPFile(remote.url, session)
            zf = zipfile.ZipFile(http)
        except Exception as e:  # unreachable, no range support, not a zip...
            sources.append(f"  {key:22s} {remote.filename}: {e}")
            continue
        members = remote_zip.match_members(zf, wanted - durations.keys(), remote.destination_dir)
        matched.update(members)
        if not members:
            sources.append(f"  {key:22s} {remote.filename}: no audio files from the index")
            continue
        items = list(members.items())
        if limit:  # the limit counts files tried, read or failed, as in local mode
            items = items[: max(0, limit - len(durations) - len(errors))]

        def read(item):
            path, info = item
            try:
                return path, audio_headers.read_member(http, info), None
            except Exception as e:
                return path, None, f"{type(e).__name__}: {e}"

        results = []
        with ThreadPoolExecutor(workers) as pool:
            for i, result in enumerate(pool.map(read, items), 1):
                results.append(result)
                if i % 50 == 0 and i < len(items):  # progress for long runs
                    pace = i / (time.time() - t0)
                    print(f"    ... {i}/{len(items)} files, {pace:.1f} files/s", file=sys.stderr)
        record(results, durations, rates, errors, verbose)
        sources.append(
            f"  {key:22s} {remote.filename}  {http.size / 1e9:.2f} GB  "
            f"{len(members)} matched, {sum(1 for _, _, e in results if not e)} read  "
            f"({http.requests} requests, {http.bytes / 1e6:.1f} MB, {time.time() - t0:.1f} s)"
        )
    # Index files that no remote holds: report them like local mode reports a
    # missing file, so the counts never drop silently.
    for path in sorted(wanted - matched):
        errors[path] = "not in any readable remote"
    return durations, rates, errors, sources


def local_durations(data_home, wanted, limit, verbose):
    """Durations read from the audio files of a local copy of the dataset."""
    if not os.path.isdir(data_home):
        return {}, {}, {}, [f"  local                  {data_home}: no local copy"]
    t0 = time.time()
    paths = sorted(wanted)
    if limit:
        paths = paths[:limit]
    results = []
    for path in paths:
        try:
            results.append((path, audio_headers.read_file(os.path.join(data_home, path)), None))
        except FileNotFoundError:
            results.append((path, None, "file not found"))
        except Exception as e:
            results.append((path, None, f"{type(e).__name__}: {e}"))
    durations, rates, errors = {}, {}, {}
    record(results, durations, rates, errors, verbose)
    sources = [
        f"  local                  {data_home}  "
        f"{len(durations)} read, {len(errors)} failed ({time.time() - t0:.1f} s)"
    ]
    return durations, rates, errors, sources


# -------------------------------------------------------------------- numbers


def summarize(index, durations, rates, errors):
    """The per-dataset numbers, from the index and what was read per audio file.

    durations and rates map index audio paths to seconds and sample rate;
    errors maps the paths that could not be read to a message.
    """
    tracks = track_audio_paths(index)
    wanted = {p for paths in tracks.values() for p in paths}
    rate_counts = Counter(rates.values())

    # One number per track: its first audio file that we could read.
    per_track = {}
    for track_id, paths in tracks.items():
        for p in paths:
            if p in durations:
                per_track[track_id] = durations[p]
                break

    return {
        "n_tracks": len(index.get("tracks", {})),
        "n_tracks_with_audio": len(tracks),  # tracks whose index entry lists an audio file
        "n_tracks_counted": len(per_track),  # tracks whose audio file we actually read
        "total_seconds": round(sum(per_track.values()), 1),
        "n_audio_files": len(wanted),
        "n_audio_files_counted": len(durations),
        "all_files_seconds": round(sum(durations.values()), 1),
        # One value when every file agrees, else None and look at the counts.
        "sample_rate": next(iter(rate_counts)) if len(rate_counts) == 1 else None,
        "sample_rates": dict(rate_counts.most_common()),
        "errors": errors,
    }


def dataset_stats(name, index, remotes, workers=4, limit=None, verbose=False, data_home=None):
    """Count tracks and read every audio duration of one dataset. Returns a dict.

    index: the dataset's index dict; remotes: its REMOTES dict (may be empty).
    data_home: when given, the audio is read from that local folder instead of
    the remotes (restricted or licensed audio).
    """
    tracks = track_audio_paths(index)
    wanted = {p for paths in tracks.values() for p in paths}
    if data_home is None:
        durations, rates, errors, sources = remote_durations(remotes, wanted, workers, limit, verbose)
    else:
        durations, rates, errors, sources = local_durations(data_home, wanted, limit, verbose)
    return {"name": name, **summarize(index, durations, rates, errors), "sources": sources}


# --------------------------------------------------------------- command line


def hms(seconds):
    h, rest = divmod(int(round(seconds)), 3600)
    m, s = divmod(rest, 60)
    return f"{h}h {m:02d}m {s:02d}s"


def print_stats(stats, limit, elapsed):
    """The terminal block for one dataset."""
    print("\n".join(stats["sources"]))
    print(f"  tracks in index:        {stats['n_tracks']}")
    print(f"  with audio in index:    {stats['n_tracks_with_audio']}")
    print(f"  counted from files:     {stats['n_tracks_counted']}")
    print(f"  total duration:         {stats['total_seconds']:.0f} s = {hms(stats['total_seconds'])}")
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
        for path, error in list(stats["errors"].items())[:5]:
            print(f"    {path}: {error}")
    if limit:
        print(f"  (only the first {limit} audio files were read)")
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
    parser.add_argument("--workers", type=int, default=4, help="parallel range requests")
    parser.add_argument(
        "--limit",
        type=positive_int,
        default=None,
        help="only read the first N audio files per dataset",
    )
    parser.add_argument("--verbose", action="store_true", help="print one line per audio file")
    parser.add_argument("--json", action="store_true", help="print the result as JSON")
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

    results, rows = {}, []
    for name in names:
        t0 = time.time()
        if not args.json:
            print(name)
        try:
            ds = mirdata.initialize(name)
            data_home = os.path.join(args.datasets_dir, name) if args.local else None
            stats = dataset_stats(
                name, load_index(ds), ds.remotes or {}, args.workers, args.limit, args.verbose, data_home
            )
        except Exception as e:  # one broken loader must not stop the others
            results[name] = {"name": name, "error": f"{type(e).__name__}: {e}"}
            rows.append((name, "-", "-", "-", "-", f"{type(e).__name__}: {e}"))
            if not args.json:
                print(f"  error: {type(e).__name__}: {e}")
            continue
        results[name] = stats
        rows.append(
            (
                name,
                str(stats["n_tracks"]),
                f"{stats['n_tracks_counted']}/{stats['n_tracks_with_audio']}",
                hms(stats["total_seconds"]) if stats["n_tracks_counted"] else "-",
                str(stats["sample_rate"]) if stats["sample_rate"] else ("mixed" if stats["sample_rates"] else "-"),
                f"{len(stats['errors'])} errors" if stats["errors"] else "",
            )
        )
        if not args.json:
            print_stats(stats, args.limit, time.time() - t0)

    if args.json:
        print(json.dumps(results[names[0]] if len(names) == 1 else results, indent=2))
    elif len(names) > 1:
        print(f"\n{'dataset':36s} {'tracks':>7s} {'counted':>10s}  {'duration':>13s}  {'rate':>6s}")
        for name, n_tracks, counted, duration, rate, note in rows:
            print(f"{name:36s} {n_tracks:>7s} {counted:>10s}  {duration:>13s}  {rate:>6s}  {note}")


if __name__ == "__main__":
    main()
