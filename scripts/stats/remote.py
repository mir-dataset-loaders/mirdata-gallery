"""Reading a dataset's remotes: zips by range, its annotation files, and the remote budget.

Servers like Zenodo honour HTTP range requests ("send me bytes X to Y"), so a
zip's table of contents can be read from the end of the file and any member
from its offset, while the rest of the archive is never transferred
(HTTPFile, member_bytes, match_members).

fetch() writes a dataset's annotation and metadata files into a folder laid
out like a local copy, since mirdata's loaders read files from disk. Each
zip's file list is read first, by range, so a zip without annotation files
costs a few KB. A zip that holds some is downloaded whole up to
MAX_ARCHIVE_MB, and read file by file by range when bigger. On a server
without range support, zips up to MAX_ARCHIVE_MB are downloaded whole.
tar.gz and similar archives are reported and skipped.

Every remote read is checked against one Budget per dataset (MB and minutes).
"""

import io
import os
import struct
import sys
import threading
import time
import zipfile
import zlib
from concurrent.futures import ThreadPoolExecutor

import requests

MAX_REMOTE_MB = (
    2000  # default budget per dataset: annotation data downloaded from the remotes
)

MAX_REMOTE_MINUTES = (
    10  # default budget per dataset: time spent reading the annotation remotes
)

MAX_ARCHIVE_MB = 200  # a zip with annotation files up to this size is downloaded whole

# Archives that are not zips: they have no table of contents to read by range.
ARCHIVE_EXTENSIONS = (".tar.gz", ".tgz", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar")


class RemoteLimit(Exception):
    """The remote budget ran out: this part should be computed locally (--local)."""


class Budget:
    """How much a remote run may read (MB) and how long it may take (minutes).

    Every remote read calls check() with the bytes it is about to fetch, then
    charge() with what it got; check() raises RemoteLimit once either limit
    would be passed, so a big download is refused before it starts. None
    means no limit. Thread-safe: reads run in parallel.
    """

    def __init__(self, max_mb=None, max_minutes=None):
        self.max_mb = max_mb
        self.max_minutes = max_minutes
        self.start = time.monotonic()
        self.bytes = 0
        self._lock = threading.Lock()

    def check(self, more_bytes=0):
        if (
            self.max_minutes is not None
            and time.monotonic() - self.start > self.max_minutes * 60
        ):
            raise RemoteLimit(
                f"took longer than the {self.max_minutes} min remote limit"
            )
        if self.max_mb is not None and self.bytes + more_bytes > self.max_mb * 1e6:
            raise RemoteLimit(
                f"needs more than the {self.max_mb} MB remote limit "
                f"({(self.bytes + more_bytes) / 1e6:.1f} MB)"
            )

    def charge(self, n_bytes):
        with self._lock:
            self.bytes += n_bytes


def http_session(workers):
    """A requests session with a connection pool sized for `workers` parallel reads."""
    s = requests.Session()
    adapter = requests.adapters.HTTPAdapter(
        pool_connections=workers, pool_maxsize=workers
    )
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


class HTTPFile(io.RawIOBase):
    """A read-only, seekable file whose bytes live behind a URL.

    Every read becomes one HTTP range request for exactly the bytes asked for,
    so zipfile can read a multi-GB archive's table of contents from its tail
    while we download nothing else.
    """

    def __init__(self, url, session, budget=None):
        self.session = session
        self.url = url
        self.budget = budget  # Budget: every read is checked and charged
        head = self._request("HEAD", allow_redirects=True)
        head.raise_for_status()
        if "Content-Length" not in head.headers:
            raise IOError("server does not report the file size (no range support)")
        self.url = head.url  # follow the redirect once, not on every read
        self.size = int(head.headers["Content-Length"])
        self.pos = 0
        self.requests = 0
        self.bytes = 0
        self.ranges_ignored = (
            False  # set once the server answers a range request with the whole file
        )
        self._lock = threading.Lock()

    def _request(self, method, **kwargs):
        """One HTTP request, retried on connection errors and on 429 (rate limit).

        On 429 we wait as long as the server's Retry-After header asks, so a
        burst of requests slows down instead of failing.
        """
        status = None
        for attempt in range(6):
            wait = 2**attempt
            try:
                r = self.session.request(method, self.url, timeout=60, **kwargs)
                status = r.status_code
                if status != 429:
                    return r
                r.close()
                wait = max(wait, float(r.headers.get("Retry-After", 0)))
                print(
                    f"    (rate limited by the server, waiting {wait:.0f} s)",
                    file=sys.stderr,
                )
            except requests.ConnectionError:
                if attempt == 5:
                    raise
            time.sleep(wait)
        raise IOError(f"server kept answering {status}")

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=io.SEEK_SET):
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self.pos, io.SEEK_END: self.size}[whence]
        self.pos = base + offset
        return self.pos

    def read(self, n=-1):
        if n < 0:
            n = self.size - self.pos
        data = self.read_at(self.pos, n)
        self.pos += len(data)
        return data

    def readinto(self, buffer):
        data = self.read(len(buffer))
        buffer[: len(data)] = data
        return len(data)

    def read_at(self, offset, n):
        """Bytes [offset, offset + n) in one range request. Safe to call from threads."""
        if n <= 0 or offset >= self.size:
            return b""
        end = min(offset + n, self.size) - 1
        if self.budget:
            self.budget.check(end - offset + 1)
        # stream=True: don't read the body until we know it's a range, so a
        # server that ignores Range can't make us download the whole file.
        r = self._request(
            "GET", headers={"Range": f"bytes={offset}-{end}"}, stream=True
        )
        if r.status_code == 200:
            r.close()
            self.ranges_ignored = True
            raise IOError("server ignored the range request")
        r.raise_for_status()
        # A 206 must say which bytes it carries and carry all of them; anything
        # else would hand the parsers a wrong slice of the file.
        content_range = r.headers.get("Content-Range", "")
        if not content_range.startswith(f"bytes {offset}-{end}/"):
            r.close()
            raise IOError(
                f"unexpected Content-Range {content_range!r} for bytes {offset}-{end}"
            )
        data = r.content
        if len(data) != end - offset + 1:
            raise IOError(f"got {len(data)} bytes for a {end - offset + 1}-byte range")
        with self._lock:
            self.requests += 1
            self.bytes += len(data)
        if self.budget:
            self.budget.charge(len(data))
        return data


def member_bytes(http, info):
    """The whole content of one zip member, decompressed and CRC-checked.

    One range request for the local header plus the compressed data (the
    header's extra field is assumed to fit in 4 KB; a second request covers
    the rare case where it does not).
    """
    slack = 30 + 4096
    raw = http.read_at(info.header_offset, slack + info.compress_size)
    if raw[:4] != b"PK\x03\x04":
        raise ValueError("bad local file header")
    name_len, extra_len = struct.unpack("<HH", raw[26:30])
    start = 30 + name_len + extra_len
    data = raw[start : start + info.compress_size]
    if len(data) < info.compress_size:
        data = http.read_at(info.header_offset + start, info.compress_size)
    if info.compress_type == zipfile.ZIP_DEFLATED:
        data = zlib.decompress(data, -zlib.MAX_WBITS)
    elif info.compress_type != zipfile.ZIP_STORED:
        raise ValueError(f"unsupported zip compression {info.compress_type}")
    if zlib.crc32(data) != info.CRC:
        raise ValueError("CRC mismatch")
    return data


def match_members(zf, wanted, destination_dir=None, unpack_directories=None):
    """{index path: ZipInfo} for zip members whose path is listed in the index.

    destination_dir is the folder mirdata unpacks this zip into; index paths
    include it, zip member names don't. unpack_directories are folders inside
    the zip (often a wrapper like "Repo-master/") whose contents mirdata moves
    up into destination_dir after unpacking; they are stripped from member
    names the same way.
    """
    unpack = [d.strip("/") + "/" for d in unpack_directories or []]
    found = {}
    for info in zf.infolist():
        name = info.filename
        if (
            info.is_dir()
            or "__MACOSX/" in name
            or os.path.basename(name).startswith("._")
        ):
            continue  # macOS resource forks also end in .wav; they are not audio
        for folder in unpack:
            if name.startswith(folder):
                name = name[len(folder) :]
                break
        if destination_dir:
            name = f"{destination_dir}/{name}"
        parts = name.split("/")
        for i in range(len(parts)):  # the archive may add leading folders
            candidate = "/".join(parts[i:])
            if candidate in wanted:
                found[candidate] = info
                break
    return found


def _entry_path(value):
    """The relative path of one index entry ([path, checksum]), or None."""
    if isinstance(value, list) and value and isinstance(value[0], str) and value[0]:
        return value[0]
    return None


def annotation_paths(index):
    """Relative paths of every non-audio file in the index.

    Track and multitrack entries whose key contains "audio" are left out;
    the index's "metadata" files are always included, since many loaders
    need them to build a track. A multitrack's "tracks" entry lists its
    track ids and is not a file.
    """
    paths = set()
    for track in (index.get("tracks") or {}).values():
        for key, value in (track or {}).items():
            if "audio" not in key.lower() and _entry_path(value):
                paths.add(_entry_path(value))
    for mtrack in (index.get("multitracks") or {}).values():
        for key, value in (mtrack or {}).items():
            if key != "tracks" and "audio" not in key.lower() and _entry_path(value):
                paths.add(_entry_path(value))
    for value in (index.get("metadata") or {}).values():
        if _entry_path(value):
            paths.add(_entry_path(value))
    return paths


def _write(data_home, path, data):
    target = os.path.join(data_home, path)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "wb") as f:
        f.write(data)


def download_whole(url, session, budget=None):
    """The bytes behind url, streamed.

    budget (a Budget) is checked against the size the server announces before
    anything is read, then chunk by chunk, so the remote limit stops a download
    that would pass it.
    """
    r = session.request("GET", url, timeout=60, stream=True)
    try:
        r.raise_for_status()
        if budget and "Content-Length" in r.headers:
            budget.check(int(r.headers["Content-Length"]))  # too big: refused unread
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
    """A ZipFile over a zip downloaded whole, in memory."""
    return zipfile.ZipFile(io.BytesIO(data))


def open_zip(url, session, budget=None):
    """(ZipFile, http) for a remote zip, of which only the file list is read.

    http is the HTTPFile the members are read from by range, None when the
    server has no range support and the zip had to be downloaded whole (only
    up to MAX_ARCHIVE_MB).
    """
    try:
        http = HTTPFile(url, session, budget)
    except IOError:  # no size, no range support: GitHub archives, some web servers
        return whole_zip(download_whole(url, session, budget=budget)), None
    try:
        zf = zipfile.ZipFile(http)  # the file list only, read from the end of the zip
    except Exception:  # zipfile reports a failed read as BadZipFile, hence the flag
        if not http.ranges_ignored or http.size > MAX_ARCHIVE_MB * 1e6:
            raise
        return whole_zip(download_whole(http.url, session, budget=budget)), None
    return zf, http


def source_line(key, remote, text):
    """One line of the fetch log: which remote, then what happened to it."""
    return f"  {key:22s} {remote.filename}: {text}"


def write_members(members, read, data_home, workers=1, verbose=False):
    """Write each zip member to data_home/<index path>; members is {index path: ZipInfo}.

    read(info) gives one member's bytes. Returns (written, failed, limit_hit):
    the paths now on disk, {path: why it failed}, and the RemoteLimit message
    if the budget ran out (those paths are not in failed: the limit is
    reported once).
    """

    def write(item):
        path, info = item
        try:
            _write(data_home, path, read(info))
            return path, None
        except RemoteLimit as e:
            return path, e
        except Exception as e:
            return path, f"{type(e).__name__}: {e}"

    written, failed, limit_hit = set(), {}, None
    with ThreadPoolExecutor(workers) as pool:
        for i, (path, error) in enumerate(pool.map(write, members.items()), 1):
            if isinstance(error, RemoteLimit):
                limit_hit = limit_hit or str(error)
                continue
            if error:
                failed[path] = error
            else:
                written.add(path)
            if verbose:
                print(f"    {path}: {error or 'ok'}", file=sys.stderr)
            if i % 200 == 0 and i < len(members):
                print(f"    ... {i}/{len(members)} files", file=sys.stderr)
    return written, failed, limit_hit


def fetch_zip(remote, todo, data_home, session, budget=None, workers=4, verbose=False):
    """The todo paths a zip remote holds: (held, written, failed, limit_hit, log text).

    Only the zip's file list is read first. A zip holding todo paths is then
    downloaded whole up to MAX_ARCHIVE_MB, and read file by file by range when
    bigger. held is every todo path the zip holds, written or not.
    """
    t0 = time.time()
    zf, http = open_zip(remote.url, session, budget)
    members = match_members(
        zf, todo, remote.destination_dir, getattr(remote, "unpack_directories", None)
    )
    if not members:
        return set(), set(), {}, None, "no annotation files from the index"
    if http and http.size <= MAX_ARCHIVE_MB * 1e6:
        # Small: one download instead of a request per file. It is the same zip,
        # so the members found above fit it.
        zf, http = whole_zip(download_whole(http.url, session, budget)), None
    if http:
        read = lambda info: member_bytes(http, info)  # noqa: E731
        written, failed, limit_hit = write_members(
            members, read, data_home, workers, verbose
        )
        how = f"{http.requests} requests, {http.bytes / 1e6:.1f} MB"
        size = f"{http.size / 1e9:.2f} GB"
    else:  # in memory: no threads needed
        written, failed, limit_hit = write_members(
            members, zf.read, data_home, 1, verbose
        )
        how = "downloaded whole"
        size = f"{sum(i.compress_size for i in zf.infolist()) / 1e9:.2f} GB"
    text = (
        f"{size}  {len(members)} matched, {len(written)} fetched  "
        f"({how}, {time.time() - t0:.1f} s)"
    )
    return set(members), written, failed, limit_hit, text


def fetch_file(remote, todo, data_home, session, budget=None):
    """A plain-file remote, downloaded whole when it is a todo path: (held, written, failed, limit_hit, log text)."""
    path = (
        f"{remote.destination_dir}/{remote.filename}"
        if remote.destination_dir
        else remote.filename
    )
    if path not in todo:
        return set(), set(), {}, None, "not an annotation file of the index"
    data = download_whole(remote.url, session, budget)
    _write(data_home, path, data)
    return {path}, {path}, {}, None, f"{len(data) / 1e6:.1f} MB downloaded"


def closing_problems(remotes, unmatched, unreadable, limit_hit):
    """The reason to run locally once every remote is done, if any (a list of at most one).

    After the limit, the unread remotes explain the unmatched files, so only
    the limit is reported.
    """
    if not remotes:
        return ["no remotes: the annotations have to be downloaded manually"]
    if limit_hit:
        return [f"remote limit: {limit_hit}"]
    if unmatched:
        why = f"; not readable: {'; '.join(unreadable)}" if unreadable else ""
        return [
            f"{len(unmatched)} annotation files not found in the readable remotes{why}"
        ]
    return []


def fetch(remotes, wanted, data_home, workers=4, verbose=False, budget=None):
    """Write the wanted index paths found in the remotes under data_home.

    Returns (fetched, errors, sources, problems): the paths now on disk, why the
    others are missing, one log line per remote, and the reasons to run locally.
    """
    present = {p for p in wanted if os.path.isfile(os.path.join(data_home, p))}
    fetched, errors, sources = set(present), {}, []
    if present:
        sources.append(f"  {'cached':22s} {len(present)} files already in {data_home}")
    if not remotes:
        sources.append("  (no remotes: the annotations have to be downloaded manually)")
    session = http_session(workers)
    matched = set(present)  # every wanted path some remote holds, fetched or not
    unreadable = []  # "remote: why" for remotes that cannot be read
    limit_hit = None  # the RemoteLimit message, once the budget ran out

    for key, remote in (remotes or {}).items():
        todo = wanted - fetched
        if not todo:
            break
        name = remote.filename.lower()
        if limit_hit:
            sources.append(source_line(key, remote, f"not read, {limit_hit}"))
            continue
        if name.endswith(ARCHIVE_EXTENSIONS):
            sources.append(source_line(key, remote, "not a zip, skipped"))
            unreadable.append(f"{remote.filename} cannot be read remotely (not a zip)")
            continue
        try:
            if name.endswith(".zip"):
                held, written, failed, limit_hit, text = fetch_zip(
                    remote, todo, data_home, session, budget, workers, verbose
                )
            else:
                held, written, failed, limit_hit, text = fetch_file(
                    remote, todo, data_home, session, budget
                )
        except RemoteLimit as e:
            limit_hit = text = str(e)
        except Exception as e:  # no access, no range support, not a zip...
            text = f"{type(e).__name__}: {e}"
            unreadable.append(f"{remote.filename}: {text}")
        else:
            matched |= held
            fetched |= written
            errors.update(failed)
        sources.append(source_line(key, remote, text))

    unmatched = sorted(wanted - matched)
    for path in unmatched:
        errors[path] = "not in any readable remote"
    problems = closing_problems(remotes, unmatched, unreadable, limit_hit)
    return fetched, errors, sources, problems
