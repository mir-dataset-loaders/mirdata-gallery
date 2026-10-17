"""Read pieces of a zip archive straight from its URL, without downloading it.

Servers like Zenodo honour HTTP range requests ("send me bytes X to Y"), so a
zip's table of contents can be read from the end of the file and any member
from its offset, while the rest of the archive is never transferred. The
annotation stats use this to pull annotation files out of multi-GB dataset
archives.
"""

import io
import os
import struct
import sys
import threading
import time
import zipfile
import zlib

import requests


# Archives that are not zips: they have no table of contents to read by range.
ARCHIVE_EXTENSIONS = (".tar.gz", ".tgz", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar")


def session(workers):
    """A requests session with a connection pool sized for `workers` parallel reads."""
    s = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=workers, pool_maxsize=workers)
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
        self.budget = budget  # stats.common.Budget: every read is checked and charged
        head = self._request("HEAD", allow_redirects=True)
        head.raise_for_status()
        if "Content-Length" not in head.headers:
            raise IOError("server does not report the file size (no range support)")
        self.url = head.url  # follow the redirect once, not on every read
        self.size = int(head.headers["Content-Length"])
        self.pos = 0
        self.requests = 0
        self.bytes = 0
        self.ranges_ignored = False  # set once the server answers a range request with the whole file
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
                print(f"    (rate limited by the server, waiting {wait:.0f} s)", file=sys.stderr)
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
        r = self._request("GET", headers={"Range": f"bytes={offset}-{end}"}, stream=True)
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
            raise IOError(f"unexpected Content-Range {content_range!r} for bytes {offset}-{end}")
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
        if info.is_dir() or "__MACOSX/" in name or os.path.basename(name).startswith("._"):
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
