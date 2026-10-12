"""Fetch only the annotation and metadata files of a dataset from its remotes.

annotation_stats.py runs mirdata's own loaders, which read files from disk.
In remote mode this module puts exactly the files those loaders need into a
folder laid out like a local copy (data_home), without downloading the
audio: the dataset index lists every file by its path relative to data_home,
and every non-audio file is wanted. A zip remote up to MAX_ARCHIVE_MB is
downloaded whole into memory in one request (faster than hundreds of range
requests, which servers like Zenodo rate-limit); a bigger one, typically
audio and annotations bundled together, is read with HTTP range requests
(see remote_zip.py), so only the wanted files are transferred. A small zip
whose server cannot answer range requests (GitHub's generated archives, a
common home for annotations) is downloaded whole too. A remote that is a
plain file listed in the index is fetched whole. Other archives (tar.gz,
...) cannot be read by range and are reported and skipped, as in
audio_stats.py.

Files already in data_home are kept, so a fetch folder can be reused.
"""

import io
import os
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor

import requests

import remote_zip

MAX_FILE_MB = 50  # a single annotation file bigger than this is skipped (features, not labels)
MAX_ARCHIVE_MB = 200  # a zip up to this size is downloaded whole; bigger ones are read by range
ARCHIVE_EXTENSIONS = (".tar.gz", ".tgz", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar")


def _entry_path(value):
    """The relative path of one index entry ([path, checksum]), or None."""
    if isinstance(value, list) and value and isinstance(value[0], str) and value[0]:
        return value[0]
    return None


def annotation_paths(index, track_ids=None):
    """Relative paths of every non-audio file in the index.

    Track and multitrack entries whose key contains "audio" are left out;
    the index's "metadata" files are always included, since many loaders
    need them to build a track. track_ids limits the track entries to those
    tracks (multitracks and metadata are kept whole).
    """
    paths = set()
    tracks = index.get("tracks", {})
    for track_id in tracks if track_ids is None else track_ids:
        for key, value in tracks.get(track_id, {}).items():
            if "audio" not in key.lower() and _entry_path(value):
                paths.add(_entry_path(value))
    for mtrack in index.get("multitracks", {}).values():
        for key, value in mtrack.items():
            if "audio" not in key.lower() and _entry_path(value):
                paths.add(_entry_path(value))
    for value in index.get("metadata", {}).values():
        if _entry_path(value):
            paths.add(_entry_path(value))
    return paths


def _write(data_home, path, data):
    target = os.path.join(data_home, path)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "wb") as f:
        f.write(data)


def _session(workers):
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=workers, pool_maxsize=workers)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def download_whole(url, session, max_mb=None):
    """The bytes behind url, streamed; an IOError past max_mb so a big archive is never pulled."""
    max_mb = MAX_ARCHIVE_MB if max_mb is None else max_mb
    r = session.request("GET", url, timeout=60, stream=True)
    try:
        r.raise_for_status()
        chunks, size = [], 0
        for chunk in r.iter_content(1 << 20):
            size += len(chunk)
            if size > max_mb * 1e6:
                raise IOError(f"over {max_mb} MB without range support, not downloaded whole")
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        r.close()


def open_zip(url, session):
    """(ZipFile, read(info) -> bytes, http) for a remote zip.

    http is the HTTPFile when members are read by range, None when the zip
    was downloaded whole: because it is small, or because the server has no
    range support.
    """
    try:
        http = remote_zip.HTTPFile(url, session)
    except IOError:  # no size, no range support: GitHub archives, some web servers
        data = download_whole(url, session)
    else:
        if http.size > MAX_ARCHIVE_MB * 1e6:
            zf = zipfile.ZipFile(http)
            return zf, lambda info: remote_zip.member_bytes(http, info), http
        data = http.read_at(0, http.size)  # small: one request for everything
    zf = zipfile.ZipFile(io.BytesIO(data))
    return zf, zf.read, None  # ZipFile.read checks the CRC itself


def fetch(remotes, wanted, data_home, workers=4, max_file_mb=MAX_FILE_MB, verbose=False):
    """Write the wanted index paths found in the remotes under data_home.

    remotes: {key: RemoteFileMetadata}, as in a loader's REMOTES dict.
    Returns (fetched, errors, sources): the set of paths now on disk, {path:
    why it is missing}, and one summary line per remote.
    """
    present = {p for p in wanted if os.path.isfile(os.path.join(data_home, p))}
    fetched, errors, sources = set(present), {}, []
    if present:
        sources.append(f"  {'cached':22s} {len(present)} files already in {data_home}")
    if not remotes:
        sources.append("  (no remotes: the annotations have to be obtained manually)")
    max_bytes = max_file_mb * 1e6
    session = _session(workers)
    matched = set(present)  # every wanted path some remote holds, fetched or not

    for key, remote in (remotes or {}).items():
        todo = wanted - fetched
        if not todo:
            break
        name = remote.filename.lower()
        t0 = time.time()
        if name.endswith(".zip"):
            try:
                zf, read_member, http = open_zip(remote.url, session)
                members = remote_zip.match_members(zf, todo, remote.destination_dir)
            except Exception as e:  # unreachable, no range support, not a zip...
                sources.append(f"  {key:22s} {remote.filename}: {type(e).__name__}: {e}")
                continue
            matched.update(members)
            if not members:
                sources.append(f"  {key:22s} {remote.filename}: no annotation files from the index")
                continue
            items = []
            for path, info in members.items():
                if info.file_size > max_bytes:
                    errors[path] = f"{info.file_size / 1e6:.0f} MB, over the {max_file_mb} MB limit"
                else:
                    items.append((path, info))

            def read(item):
                path, info = item
                try:
                    _write(data_home, path, read_member(info))
                    return path, None
                except Exception as e:
                    return path, f"{type(e).__name__}: {e}"

            n_ok = 0
            with ThreadPoolExecutor(workers if http else 1) as pool:  # in memory: no need
                for i, (path, error) in enumerate(pool.map(read, items), 1):
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
        elif name.endswith(ARCHIVE_EXTENSIONS):
            sources.append(f"  {key:22s} {remote.filename}: not a zip, skipped")
        else:  # a plain file: fetched whole if the index lists it
            path = f"{remote.destination_dir}/{remote.filename}" if remote.destination_dir else remote.filename
            if path not in todo:
                sources.append(f"  {key:22s} {remote.filename}: not an annotation file of the index")
                continue
            matched.add(path)
            try:
                http = remote_zip.HTTPFile(remote.url, session)
                if http.size > max_bytes:
                    raise ValueError(f"{http.size / 1e6:.0f} MB, over the {max_file_mb} MB limit")
                _write(data_home, path, http.read_at(0, http.size))
                fetched.add(path)
                sources.append(f"  {key:22s} {remote.filename}  {http.size / 1e6:.1f} MB fetched")
            except Exception as e:
                errors[path] = f"{type(e).__name__}: {e}"
                sources.append(f"  {key:22s} {remote.filename}: {errors[path]}")

    for path in sorted(wanted - matched):
        errors[path] = "not in any readable remote"
    return fetched, errors, sources
