"""Fetch a dataset's annotation and metadata files from its remotes, without the audio.

mirdata's loaders read files from disk, so the files the index lists are
written into a folder laid out like a local copy. Each zip's file list is read
first, by range (remote_zip.py), so a zip without annotation files costs a few
KB. A zip that holds some is downloaded whole up to MAX_ARCHIVE_MB, and read
file by file by range when bigger. On a server without range support, zips up
to MAX_ARCHIVE_MB are downloaded whole. tar.gz and similar archives are
reported and skipped.
"""

import io
import os
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor


from stats import remote_zip
from stats.common import RemoteLimit, remote_problems

MAX_ARCHIVE_MB = 200  # a zip with annotation files up to this size is downloaded whole


def _entry_path(value):
    """The relative path of one index entry ([path, checksum]), or None."""
    if isinstance(value, list) and value and isinstance(value[0], str) and value[0]:
        return value[0]
    return None


def annotation_paths(index, track_ids=None):
    """Relative paths of every non-audio file in the index.

    Track and multitrack entries whose key contains "audio" are left out;
    the index's "metadata" files are always included, since many loaders
    need them to build a track. A multitrack's "tracks" entry lists its
    track ids and is not a file. track_ids limits the track entries to those
    tracks and the multitracks to those containing one of them.
    """
    paths = set()
    tracks = index.get("tracks") or {}
    for track_id in tracks if track_ids is None else track_ids:
        for key, value in (tracks.get(track_id) or {}).items():
            if "audio" not in key.lower() and _entry_path(value):
                paths.add(_entry_path(value))
    selected = None if track_ids is None else set(track_ids)
    for mtrack in (index.get("multitracks") or {}).values():
        mtrack = mtrack or {}
        members = mtrack.get("tracks")  # the multitrack's track ids, not a file entry
        if selected is not None and isinstance(members, list) and not selected & set(members):
            continue  # with a limit, only multitracks of the selected tracks
        for key, value in mtrack.items():
            if key != "tracks" and "audio" not in key.lower() and _entry_path(value):
                paths.add(_entry_path(value))
    for value in (index.get("metadata") or {}).values():
        if _entry_path(value):
            paths.add(_entry_path(value))
    return paths


def index_notes(index):
    """Log lines for index sections that are present but null (billboard's "metadata": null)."""
    return [
        f"  {'index':22s} \"{section}\" is null: no {section} files listed"
        for section in ("tracks", "multitracks", "metadata")
        if section in index and index[section] is None
    ]


def _write(data_home, path, data):
    target = os.path.join(data_home, path)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "wb") as f:
        f.write(data)


def download_whole(url, session, budget=None):
    """The bytes behind url, streamed.

    budget (a stats.common.Budget) is checked and charged chunk by chunk, so
    the remote limit stops a download that would pass it.
    """
    r = session.request("GET", url, timeout=60, stream=True)
    try:
        r.raise_for_status()
        chunks = []
        for chunk in r.iter_content(1 << 20):
            if budget:
                budget.check(len(chunk))
                budget.charge(len(chunk))
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        r.close()


def whole_zip(data):
    """(ZipFile, read(info) -> bytes, None) for a zip downloaded whole."""
    zf = zipfile.ZipFile(io.BytesIO(data))
    return zf, zf.read, None  # ZipFile.read checks the CRC itself


def open_zip(url, session, budget=None):
    """(ZipFile, read(info) -> bytes, http) for a remote zip, of which only the file list is read.

    http is the HTTPFile the members are read from by range, None when the
    server has no range support and the zip had to be downloaded whole (only
    up to MAX_ARCHIVE_MB).
    """
    try:
        http = remote_zip.HTTPFile(url, session, budget)
    except IOError:  # no size, no range support: GitHub archives, some web servers
        return whole_zip(download_whole(url, session, budget=budget))
    try:
        zf = zipfile.ZipFile(http)  # the file list only, read from the end of the zip
    except Exception:  # zipfile reports a failed read as BadZipFile, hence the flag
        if not http.ranges_ignored or http.size > MAX_ARCHIVE_MB * 1e6:
            raise
        return whole_zip(download_whole(http.url, session, budget=budget))
    return zf, lambda info: remote_zip.member_bytes(http, info), http


def fetch(remotes, wanted, data_home, workers=4, verbose=False, budget=None):
    """Write the wanted index paths found in the remotes under data_home.

    Returns (fetched, errors, sources, problems): the paths now on disk, why the
    others are missing, one log line per remote, and the reasons to run locally.
    """
    present = {p for p in wanted if os.path.isfile(os.path.join(data_home, p))}
    fetched, errors, sources, problems = set(present), {}, [], []
    if present:
        sources.append(f"  {'cached':22s} {len(present)} files already in {data_home}")
    if not remotes:
        reason = "no remotes: the annotations have to be downloaded manually"
        sources.append(f"  ({reason})")
        problems.append(reason)
    session = remote_zip.session(workers)
    matched = set(present)  # every wanted path some remote holds, fetched or not
    unreadable = []  # "remote: why" for remotes that cannot be read
    limit_hit = None  # the RemoteLimit message, once the budget ran out

    for key, remote in (remotes or {}).items():
        todo = wanted - fetched
        if not todo:
            break
        name = remote.filename.lower()
        t0 = time.time()
        if limit_hit:
            sources.append(f"  {key:22s} {remote.filename}: not read, {limit_hit}")
            continue
        if name.endswith(".zip"):
            try:
                zf, read_member, http = open_zip(remote.url, session, budget)
                members = remote_zip.match_members(
                    zf, todo, remote.destination_dir, getattr(remote, "unpack_directories", None)
                )
                if members and http and http.size <= MAX_ARCHIVE_MB * 1e6:
                    # Small and holding annotation files: one download instead of a request per
                    # file. It is the same zip, so the members found above fit it.
                    zf, read_member, http = whole_zip(download_whole(http.url, session, budget))
            except RemoteLimit as e:
                limit_hit = str(e)
                sources.append(f"  {key:22s} {remote.filename}: {e}")
                continue
            except Exception as e:  # no access, no range support, not a zip...
                sources.append(f"  {key:22s} {remote.filename}: {type(e).__name__}: {e}")
                unreadable.append(f"{remote.filename}: {type(e).__name__}: {e}")
                continue
            matched.update(members)
            if not members:
                sources.append(f"  {key:22s} {remote.filename}: no annotation files from the index")
                continue
            items = list(members.items())

            def read(item):
                path, info = item
                try:
                    _write(data_home, path, read_member(info))
                    return path, None
                except RemoteLimit as e:
                    return path, e
                except Exception as e:
                    return path, f"{type(e).__name__}: {e}"

            n_ok = 0
            with ThreadPoolExecutor(workers if http else 1) as pool:  # in memory: no need
                for i, (path, error) in enumerate(pool.map(read, items), 1):
                    if isinstance(error, RemoteLimit):
                        limit_hit = limit_hit or str(error)
                        continue  # not fetched; reported once as a problem
                    if error:
                        errors[path] = error
                    else:
                        fetched.add(path)
                        n_ok += 1
                    if verbose:
                        print(f"    {path}: {error or 'ok'}", file=sys.stderr)
                    if i % 200 == 0 and i < len(items):
                        print(f"    ... {i}/{len(items)} files", file=sys.stderr)
            if http:
                how = f"{http.requests} requests, {http.bytes / 1e6:.1f} MB"
                size = f"{http.size / 1e9:.2f} GB"
            else:
                how = "downloaded whole"
                size = f"{sum(i.compress_size for i in zf.infolist()) / 1e9:.2f} GB"
            sources.append(
                f"  {key:22s} {remote.filename}  {size}  {len(members)} matched, {n_ok} fetched  "
                f"({how}, {time.time() - t0:.1f} s)"
            )
        elif name.endswith(remote_zip.ARCHIVE_EXTENSIONS):
            sources.append(f"  {key:22s} {remote.filename}: not a zip, skipped")
            unreadable.append(f"{remote.filename} cannot be read remotely (not a zip)")
        else:  # a plain file: fetched whole if the index lists it
            path = f"{remote.destination_dir}/{remote.filename}" if remote.destination_dir else remote.filename
            if path not in todo:
                sources.append(f"  {key:22s} {remote.filename}: not an annotation file of the index")
                continue
            matched.add(path)
            try:
                try:
                    http = remote_zip.HTTPFile(remote.url, session, budget)
                except IOError:  # no size, no range support: stream it whole, capped
                    data = download_whole(remote.url, session, budget)
                    how = "no range support, downloaded whole"
                else:
                    data = http.read_at(0, http.size)
                    how = "fetched"
                _write(data_home, path, data)
                fetched.add(path)
                sources.append(f"  {key:22s} {remote.filename}  {len(data) / 1e6:.1f} MB {how}")
            except RemoteLimit as e:
                limit_hit = str(e)
                sources.append(f"  {key:22s} {remote.filename}: {e}")
            except Exception as e:
                errors[path] = f"{type(e).__name__}: {e}"
                sources.append(f"  {key:22s} {remote.filename}: {errors[path]}")
                unreadable.append(f"{remote.filename}: {errors[path]}")

    unmatched = sorted(wanted - matched)
    for path in unmatched:
        errors[path] = "not in any readable remote"
    # Without remotes, "no remotes" above already explains the unmatched files.
    problems += remote_problems("annotation", limit_hit, unmatched if remotes else [], unreadable)
    if not unmatched and not limit_hit and unreadable and wanted - fetched:
        problems.append("; ".join(unreadable))  # matched files that failed to download
    return fetched, errors, sources, problems
