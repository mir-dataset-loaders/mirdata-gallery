"""Reading audio durations and sample rates: from zip remotes by range, or from a local copy."""

import os
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor


from stats import remote_zip
from stats.audio import headers
from stats.common import RemoteLimit, remote_problems


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


def remote_durations(remotes, wanted, workers, limit, verbose, budget=None):
    """Durations read by range requests from the dataset's zip remotes.

    Returns (durations, rates, errors, sources, problems). problems are the
    reasons to run locally (no remotes, unreadable remotes, the budget); a file
    that fails to parse is an error instead, as it would fail locally too.
    """
    if not remotes:
        reason = "no remotes: the audio has to be downloaded manually"
        return {}, {}, {}, [f"  ({reason})"], [reason]
    session = remote_zip.session(workers)

    durations, rates, errors, sources = {}, {}, {}, []
    unreadable = []  # "remote: why" for remotes that could hold audio but cannot be read
    limit_hit = None  # the RemoteLimit message, once the budget ran out
    matched = set()  # every index path some remote contains, read or not
    for key, remote in remotes.items():
        name = remote.filename.lower()
        if not name.endswith(".zip"):
            sources.append(f"  {key:22s} {remote.filename}: not a zip, skipped")
            if name.endswith(remote_zip.ARCHIVE_EXTENSIONS):
                unreadable.append(f"{remote.filename} cannot be read remotely (not a zip)")
            continue
        if limit_hit:
            sources.append(f"  {key:22s} {remote.filename}: not read, {limit_hit}")
            continue
        t0 = time.time()
        try:
            http = remote_zip.HTTPFile(remote.url, session, budget)
            zf = zipfile.ZipFile(http)
        except RemoteLimit as e:
            limit_hit = str(e)
            sources.append(f"  {key:22s} {remote.filename}: {e}")
            continue
        except Exception as e:  # no access, no range support, not a zip...
            sources.append(f"  {key:22s} {remote.filename}: {e}")
            unreadable.append(f"{remote.filename}: {type(e).__name__}: {e}")
            continue
        members = remote_zip.match_members(
            zf,
            wanted - durations.keys(),
            remote.destination_dir,
            getattr(remote, "unpack_directories", None),
        )
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
                return path, headers.read_member(http, info), None
            except RemoteLimit as e:
                return path, None, e
            except Exception as e:
                return path, None, f"{type(e).__name__}: {e}"

        results = []
        with ThreadPoolExecutor(workers) as pool:
            for i, result in enumerate(pool.map(read, items), 1):
                if isinstance(result[2], RemoteLimit):
                    limit_hit = limit_hit or str(result[2])
                    continue  # not read; reported once as a problem, not per file
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
    unmatched = sorted(wanted - matched)
    for path in unmatched:
        errors[path] = "not in any readable remote"
    problems = remote_problems("audio", limit_hit, unmatched, unreadable)
    return durations, rates, errors, sources, problems


def local_durations(data_home, wanted, limit, verbose):
    """Durations read from the audio files of a local copy of the dataset.

    Returns (durations, rates, errors, sources, problems); problems is always
    empty, a local run having nowhere else to go. (stats.dataset.compute
    checks that the local copy exists.)
    """
    t0 = time.time()
    paths = sorted(wanted)
    if limit:
        paths = paths[:limit]
    results = []
    for path in paths:
        try:
            results.append((path, headers.read_file(os.path.join(data_home, path)), None))
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
    return durations, rates, errors, sources, []
