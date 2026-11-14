"""Fetch the non-audio files of a dataset from its remotes.

mirdata's loaders read files from disk, so fetch() writes the files the index
lists, all but the audio, into a folder laid out like a local copy. Plain
files are all downloaded; archives are read smallest first, only while files
are missing. A zip is read file by file by range when it holds audio and
downloaded whole when it does not; a tar is streamed. Every download counts
against one Budget per dataset (MAX_DOWNLOAD_MB).
"""

import hashlib
import io
import os
import struct
import sys
import tarfile
import tempfile
import threading
import time
import types
import unicodedata
import zipfile
import zlib
from concurrent.futures import ThreadPoolExecutor

import requests

MAX_DOWNLOAD_MB = 8000  # budget per dataset: bytes downloaded from its remotes


# ---- Budget ----


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

    def fits(self, more_bytes):
        """Tell whether a download fits in what is left of the budget.

        Args:
            more_bytes (int): how many bytes would be downloaded

        Returns:
            bool: True when the bytes so far plus more_bytes stay within max_mb

        """
        return self.max_mb is None or self.bytes + more_bytes <= self.max_mb * 1e6

    def check(self, more_bytes):
        """Refuse a download that would pass the limit.

        Args:
            more_bytes (int): how many bytes are about to be downloaded

        Raises:
            BudgetExceeded: the bytes so far plus more_bytes pass max_mb

        """
        if not self.fits(more_bytes):
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


# ---- HTTP ----


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

    # The standard file methods zipfile calls. No request is sent until read().

    def readable(self):
        """Always True."""
        return True

    def seekable(self):
        """Always True."""
        return True

    def tell(self):
        """The current read position."""
        return self.pos

    def seek(self, offset, whence=io.SEEK_SET):
        """Move the read position, as io does."""
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self.pos, io.SEEK_END: self.size}[whence]
        self.pos = base + offset
        return self.pos

    def read(self, length=-1):
        """Read from the current position with one range request (-1: to the end)."""
        if length < 0:
            length = self.size - self.pos
        data = self.read_at(self.pos, length)
        self.pos += len(data)
        return data

    def readinto(self, buffer):
        """Fill buffer from the current position, as io.RawIOBase expects."""
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


def download_to_file(url, file, session, budget=None):
    """Download a URL into an open file, streamed and counted against the budget.

    The budget is checked against the size the server announces before
    anything is downloaded, then chunk by chunk, so a download that would pass
    it stops.

    Args:
        url (str): the file's URL
        file (file object): a file on disk, opened for binary writing
        session (requests.Session): the session the request is sent with
        budget (Budget or None): checked and added to; None means no limit

    Returns:
        int: how many bytes were written

    Raises:
        BudgetExceeded: the download would pass the budget
        requests.HTTPError: the server answered with an error

    """
    r = session.request("GET", url, timeout=60, stream=True)
    try:
        r.raise_for_status()
        if budget and "Content-Length" in r.headers:
            budget.check(int(r.headers["Content-Length"]))  # too big: refused unread
        n_bytes = 0
        for chunk in r.iter_content(1 << 20):
            if budget:
                budget.check(len(chunk))
                budget.add(len(chunk))
            file.write(chunk)
            n_bytes += len(chunk)
        return n_bytes
    finally:
        r.close()


# ---- Index paths ----


def index_paths(index):
    """Split the file paths of a dataset index into non-audio and audio.

    An index file is [path, checksum]. A track or multitrack file whose key
    contains "audio" is audio; every other one, and every file of the index's
    "metadata" (many loaders need it to build a track), is not. A multitrack's
    "tracks" entry lists its track ids and is not a file.

    Args:
        index (dict): the dataset index (stats.load_index)

    Returns:
        * set of str - the non-audio paths, relative to data_home
        * set of str - the audio paths, relative to data_home

    """
    non_audio, audio = set(), set()
    for group in ("tracks", "multitracks"):
        for entry in (index.get(group) or {}).values():
            for key, value in (entry or {}).items():
                is_file = isinstance(value, list) and value and value[0]
                if key == "tracks" or not is_file:
                    continue  # a multitrack's track ids, or no file
                (audio if "audio" in key.lower() else non_audio).add(value[0])
    for value in (index.get("metadata") or {}).values():
        if isinstance(value, list) and value and value[0]:
            non_audio.add(value[0])
    return non_audio, audio


# ---- Archive names ----


def match_name(name, wanted_by_nfc, destination_dir=None, unpack_directories=None):
    """Find the wanted index path that one archive file name stands for.

    An archive name and its index path are often written differently:

    - destination_dir is the folder mirdata unpacks the archive into; index
      paths include it, archive names don't, so it is added.
    - unpack_directories are folders inside the archive (often a wrapper like
      "Repo-master/") whose contents mirdata moves up into destination_dir;
      they are removed from the name the same way.
    - the archive may add more leading folders, so shorter and shorter tails
      of the name are tried.
    - an archive made on macOS can store "é" as two characters, so both sides
      are compared in Unicode NFC.

    Folders, and the files macOS adds (__MACOSX/, ._name), never match.

    Args:
        name (str): a file name in the archive
        wanted_by_nfc (dict): {NFC form of an index path: index path}, the
            paths to look for
        destination_dir (str or None): the folder mirdata unpacks the archive
            into, relative to data_home
        unpack_directories (list of str or None): the folders inside the
            archive whose contents mirdata moves up into destination_dir

    Returns:
        str or None: the index path, or None when the name is not wanted

    """
    if (
        name.endswith("/")
        or "__MACOSX/" in name
        or os.path.basename(name).startswith("._")
    ):
        return None  # macOS resource forks also end in .wav; they are not audio
    path = unicodedata.normalize("NFC", name)
    for folder in unpack_directories or []:
        folder = folder.strip("/") + "/"
        if path.startswith(folder):
            path = path[len(folder) :]
            break
    if destination_dir:
        path = f"{destination_dir}/{path}"
    parts = path.split("/")
    for i in range(len(parts)):  # the archive may add leading folders
        candidate = "/".join(parts[i:])
        if candidate in wanted_by_nfc:
            return wanted_by_nfc[candidate]
    return None


# ---- Saving files ----


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
        """Read and save one file, run in a worker thread.

        Args:
            item (tuple): (index path, zipfile.ZipInfo), one entry of matches

        Returns:
            * str - the index path
            * None, BudgetExceeded or str - None when saved, the
              BudgetExceeded error, or why it failed

        """
        path, member = item
        try:
            target = os.path.join(data_home, path)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "wb") as f:
                f.write(read_file(member))
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


# ---- Plain files ----


def fetch_plain(remote, data_home, session, budget=None):
    """Download a remote that is one plain file to where mirdata's download puts it.

    Every plain file is downloaded, listed in the index or not, because
    loaders also read files the index does not list (billboard's
    billboard-2.0-index.csv, good_sounds' sounds.json). A file already on disk
    is kept and not downloaded again.

    Args:
        remote (RemoteFileMetadata): the remote, a single file
        data_home (str): the dataset folder
        session (requests.Session): the session the request is sent with
        budget (Budget or None): checked and added to; None means no limit

    Returns:
        * str - the file's path relative to data_home, as the index writes it
        * str - the log message: how much was downloaded, or that the file
          was already on disk

    """
    # normpath turns a destination_dir of "." into no folder: "./x.csv" -> "x.csv"
    path = os.path.normpath(os.path.join(remote.destination_dir or "", remote.filename))
    target = os.path.join(data_home, path)
    if os.path.isfile(target):
        return path, "already on disk"
    os.makedirs(os.path.dirname(target), exist_ok=True)
    try:
        with open(target, "wb") as f:
            n_bytes = download_to_file(remote.url, f, session, budget)
    except BaseException:
        # Never leave a partial file: a later run would take it as complete
        if os.path.exists(target):
            os.remove(target)
        raise
    return path, f"{n_bytes / 1e6:.1f} MB downloaded"


# ---- Zip ----


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


def open_zip(url, session, budget=None):
    """Open a remote zip, reading only its file list when the server allows it.

    With range support, only the file list at the end of the zip is read (a
    few KB), and its files can then be read one by one by range. Without it
    (the server does not report the size, as on GitHub archives, or ignores
    range requests), the whole zip is downloaded to a temporary file on disk,
    which is deleted once the zip is closed or dropped.

    Args:
        url (str): the zip's URL
        session (requests.Session): the session the requests are sent with
        budget (Budget or None): checked and added to; None means no limit

    Returns:
        * zipfile.ZipFile - the zip
        * HTTPFile or None - the zip on the server, to read files from by
          range; None when the whole zip was downloaded

    Raises:
        BudgetExceeded: the file list, or the whole zip, would pass the budget

    """
    http = None
    try:
        http = HTTPFile(url, session, budget)
        return zipfile.ZipFile(http), http  # the file list only, read by range
    except Exception:
        # zipfile reports a failed read as BadZipFile, hence the ranges_ignored flag
        if http is not None and not http.ranges_ignored:
            raise  # a real error, not a server without range support
    zip_file = tempfile.TemporaryFile()  # on disk, deleted when closed
    download_to_file(url, zip_file, session, budget)
    return zipfile.ZipFile(zip_file), None


def fetch_zip(
    remote, remaining, audio, data_home, session, budget=None, workers=4, verbose=False
):
    """Fetch the missing index paths that a zip remote holds.

    The zip's file list is read first (by range, a few KB). A zip without
    audio is then downloaded whole in one request, unless that would pass the
    budget. A zip with audio is read file by file by range, so its audio is
    never downloaded. On a server without range support, open_zip has already
    downloaded the whole zip.

    Args:
        remote (RemoteFileMetadata): the zip remote
        remaining (set of str): the index paths still missing
        audio (set of str): the index paths of the dataset's audio files
        data_home (str): the dataset folder
        session (requests.Session): the session the requests are sent with
        budget (Budget or None): checked and added to; None means no limit
        workers (int): how many files are read by range in parallel
        verbose (bool): if True, print one line per file

    Returns:
        * set of str - the remaining paths the zip holds, saved or not
        * set of str - the paths now on disk
        * dict - {path: why it failed}
        * str or None - the BudgetExceeded message if the budget ran out
          while saving
        * str - the log message

    Raises:
        BudgetExceeded: the file list, or the files to fetch, would pass the
            budget; nothing is saved

    """
    t0 = time.time()
    zf, http = open_zip(remote.url, session, budget)

    # Match each file of the zip to the index: a wanted path, an audio file, or
    # neither.
    remaining_by_nfc = {unicodedata.normalize("NFC", p): p for p in remaining}
    audio_by_nfc = {unicodedata.normalize("NFC", p): p for p in audio}
    unpack_directories = getattr(remote, "unpack_directories", None)
    matches, has_audio = {}, False
    for member in zf.infolist():
        name = member.filename
        # Some zips store UTF-8 names without the UTF-8 flag (0x800), and zipfile
        # then reads them as cp437 ("André" becomes "Andr├⌐"). Read them back
        # as UTF-8, as mirdata's download_utils.extractall_unicode does.
        if not member.flag_bits & 0x800:
            try:
                name = name.encode("cp437").decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass  # not UTF-8 after all: keep the name as zipfile read it
        path = match_name(
            name, remaining_by_nfc, remote.destination_dir, unpack_directories
        )
        if path is not None:
            matches[path] = member
        elif match_name(name, audio_by_nfc, remote.destination_dir, unpack_directories):
            has_audio = True
    if not matches:
        return set(), set(), {}, None, "no annotation files from the index"

    zip_size = http.size if http else sum(m.compress_size for m in zf.infolist())
    if http and not has_audio and (budget is None or budget.fits(http.size)):
        # No audio: the whole zip in one request, to a temporary file on disk.
        # It is the same zip, so the members matched above fit it.
        with tempfile.TemporaryFile() as zip_file:
            download_to_file(http.url, zip_file, session, budget)
            written, failed, limit_message = save_files(
                matches, zipfile.ZipFile(zip_file).read, data_home, 1, verbose
            )
        how = "downloaded whole"
    elif http:
        # Audio, or too big to download whole: only the matched files, by range
        if budget:
            budget.check(sum(m.compress_size for m in matches.values()))
        read = lambda member: member_bytes(http, member)  # noqa: E731
        written, failed, limit_message = save_files(
            matches, read, data_home, workers, verbose
        )
        how = f"{http.requests} requests, {http.bytes / 1e6:.1f} MB"
    else:
        # No range support: open_zip has already downloaded the whole zip
        written, failed, limit_message = save_files(
            matches, zf.read, data_home, 1, verbose
        )
        how = "downloaded whole"
    text = (
        f"{zip_size / 1e9:.2f} GB  {len(matches)} matched, {len(written)} fetched  "
        f"({how}, {time.time() - t0:.1f} s)"
    )
    return set(matches), written, failed, limit_message, text


# ---- Tar ----


def fetch_tar(remote, remaining, data_home, session, budget=None):
    """Fetch the missing index paths that a tar remote holds, streamed.

    A tar has no file list to read first: its files come one after another,
    and a compressed tar (.tar.gz, .tar.bz2) is one compressed stream. So the
    archive passes through the network from its start. Each matched file is
    saved as it passes and every other file is dropped, so only the matched
    files reach the disk. The download stops early once every remaining path is
    found. A tar whose size the server reports is refused before it starts
    when it would pass the budget; the bytes are also counted as they arrive.

    A tar read to its end has its MD5 compared with the checksum in REMOTES,
    as mirdata's download does: tarfile reads a tar cut off on the server as a
    shorter tar, without an error.

    Args:
        remote (RemoteFileMetadata): the tar remote
        remaining (set of str): the index paths still missing
        data_home (str): the dataset folder
        session (requests.Session): the session the request is sent with
        budget (Budget or None): checked and added to; None means no limit

    Returns:
        * set of str - the remaining paths the tar holds, saved or not
        * set of str - the paths now on disk
        * dict - {path: why it failed}
        * None - in fetch_zip's place for the budget message: a tar raises
          BudgetExceeded instead
        * str - the log message

    Raises:
        BudgetExceeded: the tar would pass the budget
        IOError: the tar was read to its end and its MD5 is not the checksum
            in REMOTES (the tar on the server is broken)

    """
    t0 = time.time()
    wanted_by_nfc = {unicodedata.normalize("NFC", path): path for path in remaining}
    unpack_directories = getattr(remote, "unpack_directories", None)
    found, written, failed = set(), set(), {}
    counted = 0  # bytes of this download already added to the budget
    r = session.request("GET", remote.url, timeout=60, stream=True)
    md5 = hashlib.md5()  # of every byte read, to compare with the REMOTES checksum

    def read(size=-1):
        """Read from the response and add the bytes to the MD5."""
        data = r.raw.read(size)
        md5.update(data)
        return data

    try:
        r.raise_for_status()
        if budget and "Content-Length" in r.headers:
            budget.check(int(r.headers["Content-Length"]))  # too big: refused unread
        # tarfile only calls read() on the file it gets
        stream = types.SimpleNamespace(read=read)
        with tarfile.open(fileobj=stream, mode="r|*") as archive:
            for member in archive:
                if budget:  # add what the stream has read since the last file
                    budget.check(r.raw.tell() - counted)
                    budget.add(r.raw.tell() - counted)
                    counted = r.raw.tell()
                if not member.isfile():
                    continue
                path = match_name(
                    member.name,
                    wanted_by_nfc,
                    remote.destination_dir,
                    unpack_directories,
                )
                if path is None:
                    continue  # not wanted (audio...): dropped as the stream moves on
                found.add(path)
                try:
                    target = os.path.join(data_home, path)
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    with open(target, "wb") as f:
                        f.write(archive.extractfile(member).read())
                    written.add(path)
                except Exception as e:
                    failed[path] = f"{type(e).__name__}: {e}"
                if len(found) == len(remaining):
                    break  # every remaining path found: the rest is not downloaded
            else:
                # Read to its end: the MD5 can be checked once the bytes tarfile
                # left (end blocks, padding) are read too
                while read(1 << 20):
                    pass
                if remote.checksum and md5.hexdigest() != remote.checksum:
                    raise IOError(
                        "the tar's MD5 is not the checksum in REMOTES: "
                        "the tar on the server is broken"
                    )
        if budget:
            budget.add(r.raw.tell() - counted)
    finally:
        r.close()
    text = (
        f"{r.raw.tell() / 1e9:.2f} GB streamed  {len(found)} matched, "
        f"{len(written)} fetched  ({time.time() - t0:.1f} s)"
    )
    return found, written, failed, None, text


# ---- Fetch ----


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


def reasons_to_run_locally(remotes, unmatched, unreadable, limit_message):
    """Give the reason the dataset's annotation stats need a local run, if any.

    At most one reason is given. After the budget ran out, the remotes left
    unread explain the unmatched files, so only the limit is reported.

    Args:
        remotes (dict): the loader's REMOTES ({} when it has none)
        unmatched (list of str): the wanted paths no readable remote held
        unreadable (list of str): "filename: why" for each remote that could
            not be read
        limit_message (str or None): the BudgetExceeded message, if the
            budget ran out

    Returns:
        list of str: the reason, or an empty list when a local run is not needed

    """
    if not remotes:
        return ["no remotes: the annotations have to be downloaded manually"]
    if limit_message:
        return [f"remote limit: {limit_message}"]
    if unmatched:
        why = f"; not readable: {'; '.join(unreadable)}" if unreadable else ""
        return [
            f"{len(unmatched)} annotation files not found in the readable remotes{why}"
        ]
    return []


def fetch(remotes, wanted, audio, data_home, workers=4, verbose=False, budget=None):
    """Fetch a dataset's wanted index paths from its remotes into data_home.

    1. Every plain-file remote is downloaded, listed in the index or not.
    2. The archives are put in order: unknown size first, then smallest first.
    3. The archives are read in that order (fetch_zip, fetch_tar), only while
       some wanted paths are still missing.
    4. What no remote held, and the reason to run locally, are reported.

    Files already in data_home are kept. Once the budget runs out, the
    remotes not read yet are skipped.

    Args:
        remotes (dict or None): the loader's REMOTES, {key: RemoteFileMetadata}
        wanted (set of str): the index paths to fetch (index_paths: non-audio)
        audio (set of str): the index paths of the audio files (index_paths: audio)
        data_home (str): the folder to write into, laid out like a local copy
        workers (int): how many files are read by range in parallel
        verbose (bool): if True, print one line per file read from a zip
        budget (Budget or None): checked and added to; None means no limit

    Returns:
        * set of str - the wanted paths now on disk
        * dict - {path: why it is missing}
        * list of str - the log, one line per remote
        * list of str - the reason to run locally (at most one), or empty

    """
    present = {p for p in wanted if os.path.isfile(os.path.join(data_home, p))}
    fetched, errors, sources = set(present), {}, []
    if present:
        sources.append(f"  {'cached':22s} {len(present)} files already in {data_home}")
    if not remotes:
        sources.append("  (no REMOTES link found from the dataset loader.)")
    # One session for every request: it keeps connections open and reuses them
    # (no new TLS handshake per request), one connection per parallel read.
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(
        pool_connections=workers, pool_maxsize=workers
    )
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    matched = set(present)  # every wanted path some remote holds, fetched or not
    unreadable = []  # "remote: why" for remotes that cannot be read
    limit_message = None  # the BudgetExceeded message, once the budget ran out

    remotes = remotes or {}
    # An archive is a zip, a tar, or a kind that cannot be read (.7z, .rar, a
    # single .gz file). Every other remote is a plain file.
    plain_files = {
        key: remote
        for key, remote in remotes.items()
        if not remote.filename.lower().endswith(
            (".zip", ".tar", ".tgz", ".gz", ".bz2", ".xz", ".7z", ".rar")
        )
    }
    archives = {
        key: remote for key, remote in remotes.items() if key not in plain_files
    }

    # 1. Plain files: all of them, listed in the index or not
    for key, remote in plain_files.items():
        if limit_message:
            sources.append(log_line(key, remote, f"not read, {limit_message}"))
            continue
        try:
            path, text = fetch_plain(remote, data_home, session, budget)
        except BudgetExceeded as e:
            limit_message = text = str(e)
        except Exception as e:  # no access, server error...
            text = f"{type(e).__name__}: {e}"
            unreadable.append(f"{remote.filename}: {text}")
        else:
            if path in wanted:
                matched.add(path)
                fetched.add(path)
        sources.append(log_line(key, remote, text))

    # 2. Archive order: unknown size first (the server does not say, as on
    #    GitHub archives of small annotation repos), then smallest first, so
    #    an archive full of audio is opened last, often not at all
    if not wanted - fetched:
        archives = {}  # the plain files had every wanted path: no archive is opened
    archive_sizes = {}  # key -> size in bytes, None when the server does not say
    for key, remote in list(archives.items()):
        try:  # HTTPFile's HEAD retries on 429 (rate limit)
            archive_sizes[key] = HTTPFile(remote.url, session).size
        except requests.RequestException as e:  # no access, server error, no connection
            text = f"{type(e).__name__}: {e}"
            sources.append(log_line(key, remote, text))
            unreadable.append(f"{remote.filename}: {text}")
            del archives[key]
        except IOError:  # the server does not report the size
            archive_sizes[key] = None
    in_order = sorted(
        archives,
        key=lambda key: (archive_sizes[key] is not None, archive_sizes[key] or 0),
    )

    # 3. Archives: only while some wanted paths are still missing
    for key in in_order:
        remote = archives[key]
        remaining = wanted - fetched
        if not remaining:
            break
        name = remote.filename.lower()
        if limit_message:
            sources.append(log_line(key, remote, f"not read, {limit_message}"))
            continue
        if not name.endswith(
            (".zip", ".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tar.xz")
        ):
            sources.append(log_line(key, remote, "not a zip or a tar, skipped"))
            unreadable.append(
                f"{remote.filename} cannot be read remotely (not a zip or a tar)"
            )
            continue
        try:
            if name.endswith(".zip"):
                found, written, failed, limit_message, text = fetch_zip(
                    remote,
                    remaining,
                    audio,
                    data_home,
                    session,
                    budget,
                    workers,
                    verbose,
                )
            else:
                found, written, failed, limit_message, text = fetch_tar(
                    remote, remaining, data_home, session, budget
                )
        except BudgetExceeded as e:
            limit_message = text = str(e)
        except Exception as e:  # no access, no range support, a broken archive...
            text = f"{type(e).__name__}: {e}"
            unreadable.append(f"{remote.filename}: {text}")
        else:
            matched |= found
            fetched |= written
            errors.update(failed)
        sources.append(log_line(key, remote, text))

    # 4. Closing: what no remote found, and the reason to run locally
    unmatched = sorted(wanted - matched)
    for path in unmatched:
        errors[path] = "not in any readable remote"
    problems = reasons_to_run_locally(remotes, unmatched, unreadable, limit_message)
    return fetched, errors, sources, problems
