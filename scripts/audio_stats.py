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
"""

import argparse
import io
import json
import os
import struct
import sys
import threading
import time
import zipfile
import zlib
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import mirdata
import requests
from mirdata import download_utils

HEADER_BYTES = 64 * 1024  # how much of each audio file we read: enough for any header
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


# ------------------------------------------------------------------ remote zip


class HTTPFile(io.RawIOBase):
    """A read-only, seekable file whose bytes live behind a URL.

    Every read becomes one HTTP range request for exactly the bytes asked for,
    so zipfile can read a multi-GB archive's table of contents from its tail
    while we download nothing else.
    """

    def __init__(self, url, session):
        self.session = session
        self.url = url
        head = self._request("HEAD", allow_redirects=True)
        head.raise_for_status()
        if "Content-Length" not in head.headers:
            raise IOError("server does not report the file size (no range support)")
        self.url = head.url  # follow the redirect once, not on every read
        self.size = int(head.headers["Content-Length"])
        self.pos = 0
        self.requests = 0
        self.bytes = 0
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
        # stream=True: don't read the body until we know it's a range, so a
        # server that ignores Range can't make us download the whole file.
        r = self._request("GET", headers={"Range": f"bytes={offset}-{end}"}, stream=True)
        if r.status_code == 200:
            r.close()
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
        return data


def member_head(http, info):
    """The first HEADER_BYTES of one zip member, decompressed, in one range request.

    A member is stored as a local header (30 bytes + name + extra fields)
    followed by its data, deflated or stored as is. The table of contents told
    us where the member starts.
    """
    raw = http.read_at(info.header_offset, 30 + 4096 + HEADER_BYTES)
    if raw[:4] != b"PK\x03\x04":
        raise ValueError("bad local file header")
    name_len, extra_len = struct.unpack("<HH", raw[26:30])
    data = raw[30 + name_len + extra_len :]
    if info.compress_type == zipfile.ZIP_DEFLATED:
        data = zlib.decompressobj(-zlib.MAX_WBITS).decompress(data, HEADER_BYTES)
    elif info.compress_type != zipfile.ZIP_STORED:
        raise ValueError(f"unsupported zip compression {info.compress_type}")
    return data


def match_members(zf, wanted, destination_dir=None):
    """{index path: ZipInfo} for zip members that are audio files listed in the index.

    destination_dir is the folder mirdata unpacks this zip into; index paths
    include it, zip member names don't.
    """
    found = {}
    for info in zf.infolist():
        name = info.filename
        if info.is_dir() or "__MACOSX/" in name or os.path.basename(name).startswith("._"):
            continue  # macOS resource forks also end in .wav; they are not audio
        if destination_dir:
            name = f"{destination_dir}/{name}"
        parts = name.split("/")
        for i in range(len(parts)):  # the archive may add leading folders
            candidate = "/".join(parts[i:])
            if candidate in wanted:
                found[candidate] = info
                break
    return found


# -------------------------------------------------------------- header parsers


def wav_header(data, file_size):
    """(seconds, sample rate) from a RIFF/WAVE header: data chunk size / bytes per second."""
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError("not a WAV file")
    pos, sample_rate, byte_rate = 12, None, None
    while pos + 8 <= len(data):
        chunk_id = data[pos : pos + 4]
        size = struct.unpack("<I", data[pos + 4 : pos + 8])[0]
        if chunk_id == b"fmt ":
            sample_rate, byte_rate = struct.unpack("<II", data[pos + 12 : pos + 20])
        elif chunk_id == b"data":
            if not byte_rate:
                raise ValueError("data chunk before fmt chunk")
            return size / byte_rate, sample_rate
        pos += 8 + size + (size & 1)
    raise ValueError("no data chunk in the first 64 KB")


def flac_header(data, file_size):
    """(seconds, sample rate) from the STREAMINFO block that starts every FLAC file."""
    if data[:4] != b"fLaC":
        raise ValueError("not a FLAC file")
    if data[4] & 0x7F != 0:
        raise ValueError("first metadata block is not STREAMINFO")
    info = data[8:42]
    sample_rate = (info[10] << 12) | (info[11] << 4) | (info[12] >> 4)
    total_samples = ((info[13] & 0x0F) << 32) | int.from_bytes(info[14:18], "big")
    if not sample_rate or not total_samples:
        raise ValueError("STREAMINFO carries no length")
    return total_samples / sample_rate, sample_rate


MP3_BITRATES = {  # kbps for Layer III, by MPEG version then bitrate index
    True: (0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320),
    False: (0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160),
}
MP3_SAMPLE_RATES = {3: (44100, 48000, 32000), 2: (22050, 24000, 16000), 0: (11025, 12000, 8000)}


def mp3_header(data, file_size):
    """(seconds, sample rate) from the first MPEG frame.

    Variable-bitrate files carry a Xing/Info header with the frame count;
    otherwise the file is constant bitrate and duration is size / bitrate.
    """
    pos = 0
    if data[:3] == b"ID3":  # skip the ID3v2 tag at the start
        size = 0
        for b in data[6:10]:
            size = (size << 7) | (b & 0x7F)
        pos = 10 + size + (10 if data[5] & 0x10 else 0)
    while pos + 4 <= len(data):
        b1, b2, b3 = data[pos + 1], data[pos + 2], data[pos + 3]
        if data[pos] == 0xFF and b1 & 0xE0 == 0xE0:
            version = (b1 >> 3) & 3  # 3: MPEG-1, 2: MPEG-2, 0: MPEG-2.5
            layer = (b1 >> 1) & 3  # 1: Layer III
            bitrate_index, rate_index = b2 >> 4, (b2 >> 2) & 3
            if version != 1 and layer == 1 and 0 < bitrate_index < 15 and rate_index < 3:
                break
        pos += 1
    else:
        raise ValueError("no MPEG frame in the first 64 KB")
    mpeg1 = version == 3
    bitrate = MP3_BITRATES[mpeg1][bitrate_index] * 1000
    sample_rate = MP3_SAMPLE_RATES[version][rate_index]
    mono = (b3 >> 6) == 3
    xing = pos + 4 + ((17 if mono else 32) if mpeg1 else (9 if mono else 17))
    if data[xing : xing + 4] in (b"Xing", b"Info"):
        flags = struct.unpack(">I", data[xing + 4 : xing + 8])[0]
        if flags & 1:
            frames = struct.unpack(">I", data[xing + 8 : xing + 12])[0]
            return frames * (1152 if mpeg1 else 576) / sample_rate, sample_rate
    return (file_size - pos) * 8 / bitrate, sample_rate


PARSERS = {".wav": wav_header, ".flac": flac_header, ".mp3": mp3_header}


def parse_header(path, data, file_size):
    """(seconds, sample rate) of an audio file given its first bytes and its size."""
    ext = os.path.splitext(path)[1].lower()
    if ext not in PARSERS:
        raise ValueError(f"no parser for {ext}")
    return PARSERS[ext](data, file_size)


def read_member(http, info):
    """(seconds, sample rate) of one audio file inside a remote zip."""
    return parse_header(info.filename, member_head(http, info), info.file_size)


def read_file(path):
    """(seconds, sample rate) of one audio file on disk; reads only its first HEADER_BYTES."""
    with open(path, "rb") as f:
        return parse_header(path, f.read(HEADER_BYTES), os.path.getsize(path))


# -------------------------------------------------------------------- driver


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
            http = HTTPFile(remote.url, session)
            zf = zipfile.ZipFile(http)
        except Exception as e:  # unreachable, no range support, not a zip...
            sources.append(f"  {key:22s} {remote.filename}: {e}")
            continue
        members = match_members(zf, wanted - durations.keys(), remote.destination_dir)
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
                return path, read_member(http, info), None
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
            results.append((path, read_file(os.path.join(data_home, path)), None))
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


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dataset", default=None, help="one dataset (default: every dataset)")
    parser.add_argument(
        "--exclude", default="", help="comma-separated datasets to skip, e.g. acousticbrainz_genre"
    )
    parser.add_argument("--workers", type=int, default=4, help="parallel range requests")
    parser.add_argument(
        "--limit", type=int, default=None, help="only read the first N audio files per dataset"
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
