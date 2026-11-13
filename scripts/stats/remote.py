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

Every remote read is checked against one Budget per dataset (MB).
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

MAX_DOWNLOAD_MB = 8000  # budget per dataset: bytes downloaded from its remotes

MAX_ARCHIVE_MB = 200  # a zip with annotation files up to this size is downloaded whole

# Archives that are not zips: they have no table of contents to read by range.
ARCHIVE_EXTENSIONS = (".tar.gz", ".tgz", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar")


class BudgetExceeded(Exception):
    """Raised when a download would pass the dataset's budget.

    The dataset's annotation stats then need a local run (--local).

    """


class Budget:
    """How many bytes one dataset may download from its remotes.

    Every download calls check() with the bytes it is about to get, then add()
    with the bytes it got, so a download that would pass the limit is refused
    before it starts. Thread-safe: range reads run in parallel.

    Args:
        max_mb (float or None): the limit in MB; None means no limit

    Attributes:
        max_mb (float or None): the limit in MB
        bytes (int): how many bytes were downloaded so far

    """

    def __init__(self, max_mb=None):
        self.max_mb = max_mb
        self.bytes = 0
        self._lock = threading.Lock()

    def check(self, more_bytes):
        """Refuse a download that would pass the limit.

        Args:
            more_bytes (int): how many bytes are about to be downloaded

        Raises:
            BudgetExceeded: the bytes so far plus more_bytes pass max_mb

        """
        if self.max_mb is not None and self.bytes + more_bytes > self.max_mb * 1e6:
            raise BudgetExceeded(
                f"needs more than the {self.max_mb} MB download limit "
                f"({(self.bytes + more_bytes) / 1e6:.1f} MB)"
            )

    def add(self, n_bytes):
        """Count bytes that were downloaded.

        Args:
            n_bytes (int): how many bytes were just downloaded

        """
        with self._lock:
            self.bytes += n_bytes


def http_session(workers):
    """Create a requests session that keeps its connections open between requests.

    Args:
        workers (int): how many requests run in parallel; the connection pool
            keeps this many connections

    Returns:
        requests.Session: the session, for http:// and https:// URLs

    """
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
    so zipfile can read a multi-GB archive's file list from its end while
    nothing else is downloaded. A HEAD request in __init__ gets the size and
    follows redirects once.

    Args:
        url (str): the file's URL
        session (requests.Session): the session the requests are sent with
        budget (Budget or None): checked before and added to after every read;
            None means no limit

    Attributes:
        url (str): the final URL, after redirects
        size (int): the file size in bytes, from the server's Content-Length
        pos (int): the current read position
        requests (int): how many range requests were sent
        bytes (int): how many bytes were received
        ranges_ignored (bool): True once the server answered a range request
            with the whole file

    Raises:
        IOError: the HEAD request failed, or the server does not report the
            file size (so the file cannot be read by range)

    """

    def __init__(self, url, session, budget=None):
        self.session = session
        self.url = url
        self.budget = budget  # Budget: every read is checked and added
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
        """Send one HTTP request, retried on connection errors and on 429 (rate limit).

        Up to 6 attempts, waiting 1, 2, 4, ... seconds between them. On 429 it
        waits at least as long as the server's Retry-After header asks, so a
        burst of requests slows down instead of failing.

        Args:
            method (str): the HTTP method, "HEAD" or "GET"
            **kwargs: passed on to requests.Session.request (headers, stream, ...)

        Returns:
            requests.Response: the first response that is not a 429

        Raises:
            requests.ConnectionError: the last attempt could not connect
            IOError: the server answered 429 to every attempt

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
        """Tell io and zipfile that this file can be read.

        Returns:
            bool: always True

        """
        return True

    def seekable(self):
        """Tell io and zipfile that this file supports seek().

        Returns:
            bool: always True

        """
        return True

    def tell(self):
        """Get the current read position.

        Returns:
            int: the position, in bytes from the start of the file

        """
        return self.pos

    def seek(self, offset, whence=io.SEEK_SET):
        """Move the read position. No request is sent.

        Args:
            offset (int): how many bytes to move
            whence (int): where offset counts from: io.SEEK_SET (the start of
                the file), io.SEEK_CUR (the current position) or io.SEEK_END
                (the end of the file)

        Returns:
            int: the new position

        """
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self.pos, io.SEEK_END: self.size}[whence]
        self.pos = base + offset
        return self.pos

    def read(self, length=-1):
        """Read bytes from the current position with one range request.

        Args:
            length (int): how many bytes to read; -1 reads to the end of the file

        Returns:
            bytes: the bytes read, fewer than length at the end of the file

        """
        if length < 0:
            length = self.size - self.pos
        data = self.read_at(self.pos, length)
        self.pos += len(data)
        return data

    def readinto(self, buffer):
        """Read bytes from the current position into a buffer, as io.RawIOBase expects.

        Args:
            buffer (bytearray or memoryview): filled from its start; its
                length is how many bytes to read

        Returns:
            int: how many bytes were written into buffer

        """
        data = self.read(len(buffer))
        buffer[: len(data)] = data
        return len(data)

    def read_at(self, offset, length):
        """Read bytes at an offset with one range request. Safe to call from threads.

        The read position (tell) does not move. The budget is checked before
        the request and added to after it.

        Args:
            offset (int): where to start, in bytes from the start of the file
            length (int): how many bytes to read

        Returns:
            bytes: the bytes from offset to offset + length, cut at the end of
                the file; empty when length <= 0 or offset is past the end

        Raises:
            BudgetExceeded: reading them would pass the budget
            IOError: the server ignored the range request, or sent other
                bytes than the ones asked for

        """
        if length <= 0 or offset >= self.size:
            return b""
        end = min(offset + length, self.size) - 1
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
            self.budget.add(len(data))
        return data


def member_bytes(remote_zip, member):
    """Read one file out of a remote zip, decompressed and CRC-checked.

    One range request covers the file's local header and its compressed data.
    The header's length is only known once it is read, so 4 KB of slack is
    asked for; a second request covers the rare header that is longer.

    Args:
        remote_zip (HTTPFile): the zip on the server, read by range
        member (zipfile.ZipInfo): the file, from the zip's file list

    Returns:
        bytes: the file's uncompressed content

    Raises:
        ValueError: a bad local header, an unsupported compression, or a CRC
            mismatch

    """
    slack = 30 + 4096
    raw = remote_zip.read_at(member.header_offset, slack + member.compress_size)
    if raw[:4] != b"PK\x03\x04":
        raise ValueError("bad local file header")
    name_len, extra_len = struct.unpack("<HH", raw[26:30])
    start = 30 + name_len + extra_len
    data = raw[start : start + member.compress_size]
    if len(data) < member.compress_size:
        data = remote_zip.read_at(member.header_offset + start, member.compress_size)
    if member.compress_type == zipfile.ZIP_DEFLATED:
        data = zlib.decompress(data, -zlib.MAX_WBITS)
    elif member.compress_type != zipfile.ZIP_STORED:
        raise ValueError(f"unsupported zip compression {member.compress_type}")
    if zlib.crc32(data) != member.CRC:
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
    """Get the file path from one index entry.

    Args:
        value: one entry of a track in the index, normally [path, checksum];
            other values (None, a multitrack's list of track ids) are not files

    Returns:
        str or None: the path relative to data_home, or None when the entry is
            not a file

    """
    if isinstance(value, list) and value and isinstance(value[0], str) and value[0]:
        return value[0]
    return None


def annotation_paths(index):
    """Get the paths of every non-audio file in a dataset index.

    Track and multitrack entries whose key contains "audio" are left out. The
    index's "metadata" files are always included, since many loaders need them
    to build a track. A multitrack's "tracks" entry lists its track ids and is
    not a file.

    Args:
        index (dict): the dataset index (stats.load_index)

    Returns:
        set of str: the paths, relative to data_home

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


def save_file(data_home, path, data):
    """Write bytes to data_home/path, creating the folders it needs.

    Args:
        data_home (str): the dataset folder
        path (str): the file's path relative to data_home
        data (bytes): the file content

    """
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
                budget.add(len(chunk))
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


def log_line(key, remote, message):
    """Make one line of the fetch log: which remote, then what happened to it.

    Args:
        key (str): the remote's key in the loader's REMOTES
        remote (RemoteFileMetadata): the remote
        message (str): what happened to it

    Returns:
        str: the line, indented, with the key padded to 22 characters

    """
    return f"  {key:22s} {remote.filename}: {message}"


def save_files(matches, read_file, data_home, workers=1, verbose=False):
    """Read each matched archive file and save it to data_home/<index path>.

    Args:
        matches (dict): {index path: zipfile.ZipInfo}, the files to save
        read_file (callable): read_file(member) gives one file's bytes
        data_home (str): the dataset folder
        workers (int): how many files are read in parallel
        verbose (bool): if True, print one line per file

    Returns:
        * set of str - the paths now on disk
        * dict - {path: why it failed}
        * str or None - the BudgetExceeded message if the budget ran out; the
          paths it stopped are not in the dict above, the limit is reported once

    """

    def save(item):
        path, member = item
        try:
            save_file(data_home, path, read_file(member))
            return path, None
        except BudgetExceeded as e:
            return path, e
        except Exception as e:
            return path, f"{type(e).__name__}: {e}"

    written, failed, limit_message = set(), {}, None
    with ThreadPoolExecutor(workers) as pool:
        for i, (path, error) in enumerate(pool.map(save, matches.items()), 1):
            if isinstance(error, BudgetExceeded):
                limit_message = limit_message or str(error)
                continue
            if error:
                failed[path] = error
            else:
                written.add(path)
            if verbose:
                print(f"    {path}: {error or 'ok'}", file=sys.stderr)
            if i % 200 == 0 and i < len(matches):
                print(f"    ... {i}/{len(matches)} files", file=sys.stderr)
    return written, failed, limit_message


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
        read = lambda member: member_bytes(http, member)  # noqa: E731
        written, failed, limit_hit = save_files(
            members, read, data_home, workers, verbose
        )
        how = f"{http.requests} requests, {http.bytes / 1e6:.1f} MB"
        size = f"{http.size / 1e9:.2f} GB"
    else:  # in memory: no threads needed
        written, failed, limit_hit = save_files(members, zf.read, data_home, 1, verbose)
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
    save_file(data_home, path, data)
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
        sources.append("  (no REMOTES link found from the dataset loader.)")
    session = http_session(workers)
    matched = set(present)  # every wanted path some remote holds, fetched or not
    unreadable = []  # "remote: why" for remotes that cannot be read
    limit_hit = None  # the BudgetExceeded message, once the budget ran out

    for key, remote in (remotes or {}).items():
        todo = wanted - fetched
        if not todo:
            break
        name = remote.filename.lower()
        if limit_hit:
            sources.append(log_line(key, remote, f"not read, {limit_hit}"))
            continue
        if name.endswith(ARCHIVE_EXTENSIONS):
            sources.append(log_line(key, remote, "not a zip, skipped"))
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
        except BudgetExceeded as e:
            limit_hit = text = str(e)
        except Exception as e:  # no access, no range support, not a zip...
            text = f"{type(e).__name__}: {e}"
            unreadable.append(f"{remote.filename}: {text}")
        else:
            matched |= held
            fetched |= written
            errors.update(failed)
        sources.append(log_line(key, remote, text))

    unmatched = sorted(wanted - matched)
    for path in unmatched:
        errors[path] = "not in any readable remote"
    problems = closing_problems(remotes, unmatched, unreadable, limit_hit)
    return fetched, errors, sources, problems
