"""Tests for scripts/audio_stats.py using a synthetic mirdata-style dataset."""

import io
import json
import re
import struct
import sys
import wave
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import audio_stats


RESOURCES = Path(__file__).parent / "resources" / "audio_stats"
FAKE_URL = "https://example.test/fake_audio.zip"

EXPECTED_SUMMARY = {
    "n_tracks": 5,
    "n_tracks_with_audio": 4,
    "n_tracks_counted": 3,
    "total_seconds": 6.5,
    "n_audio_files": 6,
    "n_audio_files_counted": 4,
    "all_files_seconds": 10.5,
    "sample_rate": None,
    "sample_rates": {8000: 2, 16000: 1, 44100: 1},
}


# =============================================================================
# Synthetic audio and archive builders
# =============================================================================


def _make_wav(seconds=1.0, sample_rate=8000, channels=1):
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(b"\x00\x00" * int(seconds * sample_rate) * channels)
    return output.getvalue()


def _wav_with_odd_junk_chunk():
    data = _make_wav()
    junk = b"JUNK" + struct.pack("<I", 3) + b"abc" + b"\x00"
    riff_size = struct.unpack("<I", data[4:8])[0] + len(junk)
    return data[:4] + struct.pack("<I", riff_size) + data[8:12] + junk + data[12:]


def _make_flac(seconds=1.0, sample_rate=16000):
    total_samples = int(seconds * sample_rate)
    streaminfo = bytearray(34)
    packed = (
        (sample_rate << 44)
        | (0 << 41)  # one channel
        | (15 << 36)  # 16 bits per sample minus one
        | total_samples
    )
    streaminfo[10:18] = packed.to_bytes(8, "big")
    return b"fLaC" + b"\x80\x00\x00\x22" + bytes(streaminfo)


def _mp3_frame_header(version=3, bitrate_index=9, sample_rate_index=0, mono=False):
    byte_1 = 0xE0 | (version << 3) | (1 << 1) | 1
    byte_2 = bitrate_index << 4 | sample_rate_index << 2
    byte_3 = 0xC0 if mono else 0
    return bytes((0xFF, byte_1, byte_2, byte_3))


def _make_mp3_cbr(seconds=1.0, bitrate=128000):
    size = int(seconds * bitrate / 8)
    return _mp3_frame_header() + b"\x00" * (size - 4)


def _syncsafe(value):
    return bytes(
        (
            (value >> 21) & 0x7F,
            (value >> 14) & 0x7F,
            (value >> 7) & 0x7F,
            value & 0x7F,
        )
    )


def _make_mp3_with_id3(seconds=1.0):
    payload = b"abcde"
    tag = b"ID3\x04\x00\x00" + _syncsafe(len(payload)) + payload
    return tag + _make_mp3_cbr(seconds)


def _make_mp3_xing(frames=100):
    data = bytearray(48)
    data[:4] = _mp3_frame_header()
    xing = 4 + 32
    data[xing : xing + 4] = b"Xing"
    data[xing + 4 : xing + 8] = struct.pack(">I", 1)
    data[xing + 8 : xing + 12] = struct.pack(">I", frames)
    return bytes(data)


def _zip_bytes(files, compression=zipfile.ZIP_DEFLATED, prefix=""):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for path, data in files.items():
            archive.writestr(
                f"{prefix}{path}",
                data,
                compress_type=compression,
            )
    return output.getvalue()


class _BytesHTTP:
    def __init__(self, data):
        self.data = data

    def read_at(self, offset, size):
        return self.data[offset : offset + size]


class _FakeResponse:
    def __init__(self, status_code, content=b"", headers=None, url=FAKE_URL):
        self.status_code = status_code
        self.content = content
        self.headers = headers or {}
        self.url = url
        self.closed = False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise audio_stats.requests.HTTPError(f"HTTP {self.status_code}")

    def close(self):
        self.closed = True


class _FakeRangeSession:
    def __init__(
        self,
        blobs,
        *,
        include_length=True,
        ignore_range=False,
        short_range=False,
        include_content_range=True,
    ):
        self.blobs = blobs
        self.include_length = include_length
        self.ignore_range = ignore_range
        self.short_range = short_range
        self.include_content_range = include_content_range
        self.calls = []

    def mount(self, prefix, adapter):
        pass

    def request(self, method, url, timeout, **kwargs):
        self.calls.append((method, url, kwargs))
        blob = self.blobs[url]

        if method == "HEAD":
            headers = {}
            if self.include_length:
                headers["Content-Length"] = str(len(blob))
            return _FakeResponse(200, headers=headers, url=url)

        if self.ignore_range:
            return _FakeResponse(200, content=blob, url=url)

        range_header = kwargs.get("headers", {}).get("Range")
        match = re.fullmatch(r"bytes=(\d+)-(\d+)", range_header or "")
        if not match:
            raise AssertionError(f"invalid Range header: {range_header!r}")

        start, end = map(int, match.groups())
        content = blob[start : end + 1]
        if self.short_range and content:
            content = content[:-1]

        headers = {}
        if self.include_content_range:
            headers["Content-Range"] = f"bytes {start}-{end}/{len(blob)}"
        return _FakeResponse(206, content=content, headers=headers, url=url)


# =============================================================================
# Shared fake mirdata dataset
# =============================================================================


@pytest.fixture
def fake_index():
    with open(RESOURCES / "fake_index.json", encoding="utf-8") as file:
        return json.load(file)


@pytest.fixture
def fake_dataset(tmp_path, fake_index):
    data_home = tmp_path / "mir_datasets" / "fake_audio_stats"
    audio_files = {
        "audio/a.wav": _make_wav(1.0, 8000),
        "audio/b.flac": _make_flac(2.5, 16000),
        "audio/c.mp3": _make_mp3_cbr(3.0),
        "audio/d.wav": _make_wav(4.0, 8000),
        "audio/bad.wav": b"this is not a WAV file",
    }

    for relative_path, data in audio_files.items():
        path = data_home / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    index_path = tmp_path / "fake_index.json"
    index_path.write_text(json.dumps(fake_index), encoding="utf-8")

    archive = _zip_bytes(audio_files, prefix="bundle/")
    archive_path = tmp_path / "fake_audio.zip"
    archive_path.write_bytes(archive)

    return SimpleNamespace(
        index=fake_index,
        index_path=index_path,
        data_home=data_home,
        audio_files=audio_files,
        archive=archive,
        archive_path=archive_path,
    )


def _remote(filename="fake_audio.zip", url=FAKE_URL, destination_dir=None):
    return SimpleNamespace(
        filename=filename,
        url=url,
        destination_dir=destination_dir,
    )


def _assert_fake_summary(stats):
    for key, expected in EXPECTED_SUMMARY.items():
        assert stats[key] == expected
    assert set(stats["errors"]) == {
        "audio/bad.wav",
        "audio/missing.wav",
    }


# =============================================================================
# Index handling
# =============================================================================


def test_track_audio_paths_collects_all_audio_fields(fake_index):
    assert audio_stats.track_audio_paths(fake_index) == {
        "track_wav": ["audio/a.wav"],
        "track_fallback": [
            "audio/missing.wav",
            "audio/b.flac",
        ],
        "track_multi": [
            "audio/c.mp3",
            "audio/d.wav",
        ],
        "track_bad": ["audio/bad.wav"],
    }


def test_track_audio_paths_ignores_malformed_values():
    index = {
        "tracks": {
            "empty": {"audio": []},
            "none": {"audio": None},
            "string": {"audio": "audio/a.wav"},
            "annotation": {"beats": ["beats.csv", "checksum"]},
            "case": {"AuDiO": ["audio/a.wav", "checksum"]},
        }
    }
    assert audio_stats.track_audio_paths(index) == {"case": ["audio/a.wav"]}


def test_load_index_uses_existing_file(tmp_path, monkeypatch, fake_index):
    index_path = tmp_path / "index.json"
    index_path.write_text(json.dumps(fake_index), encoding="utf-8")
    dataset = SimpleNamespace(index_path=str(index_path))

    def unexpected_download(*args, **kwargs):
        raise AssertionError("existing index should not be downloaded")

    monkeypatch.setattr(
        audio_stats.download_utils,
        "download_from_remote",
        unexpected_download,
    )
    assert audio_stats.load_index(dataset) == fake_index


def test_load_index_downloads_plain_index(tmp_path, monkeypatch, fake_index):
    index_path = tmp_path / "index.json"
    dataset = SimpleNamespace(
        index_path=str(index_path),
        _index_data=SimpleNamespace(
            remote="fake remote",
            indexes_dir=str(tmp_path),
        ),
    )

    def download(remote, indexes_dir, force, cleanup):
        index_path.write_text(json.dumps(fake_index), encoding="utf-8")
        return str(index_path)

    monkeypatch.setattr(
        audio_stats.download_utils,
        "download_from_remote",
        download,
    )
    assert audio_stats.load_index(dataset) == fake_index


def test_load_index_unzips_zipped_index(tmp_path, monkeypatch, fake_index):
    index_path = tmp_path / "index.json"
    archive_path = tmp_path / "index.json.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("index.json", json.dumps(fake_index))

    dataset = SimpleNamespace(
        index_path=str(index_path),
        _index_data=SimpleNamespace(
            remote="fake remote",
            indexes_dir=str(tmp_path),
        ),
    )
    unzip_calls = []

    monkeypatch.setattr(
        audio_stats.download_utils,
        "download_from_remote",
        lambda *args: str(archive_path),
    )

    def unzip(path, cleanup):
        unzip_calls.append((path, cleanup))
        with zipfile.ZipFile(path) as archive:
            archive.extractall(tmp_path)

    monkeypatch.setattr(audio_stats.download_utils, "unzip", unzip)

    assert audio_stats.load_index(dataset) == fake_index
    assert unzip_calls == [(str(archive_path), False)]


# =============================================================================
# Header parsers
# =============================================================================


def test_wav_header_duration_and_sample_rate():
    data = _make_wav(1.25, 16000, channels=2)
    duration, sample_rate = audio_stats.wav_header(data, len(data))
    assert duration == pytest.approx(1.25)
    assert sample_rate == 16000


def test_wav_header_skips_odd_padded_chunks():
    data = _wav_with_odd_junk_chunk()
    assert audio_stats.wav_header(data, len(data)) == (1.0, 8000)


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"not a wave file", "not a WAV"),
        (_make_wav()[:36], "no data chunk"),
        (
            b"RIFF\x10\x00\x00\x00WAVE"
            b"data\x04\x00\x00\x00\x00\x00\x00\x00",
            "data chunk before fmt",
        ),
    ],
)
def test_wav_header_rejects_invalid_files(data, message):
    with pytest.raises(ValueError, match=message):
        audio_stats.wav_header(data, len(data))


def test_flac_header_duration_and_sample_rate():
    data = _make_flac(2.5, 16000)
    duration, sample_rate = audio_stats.flac_header(data, len(data))
    assert duration == pytest.approx(2.5)
    assert sample_rate == 16000


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"not flac", "not a FLAC"),
        (
            b"fLaC\x81\x00\x00\x22" + bytes(34),
            "first metadata block is not STREAMINFO",
        ),
        (_make_flac(0, 16000), "STREAMINFO carries no length"),
    ],
)
def test_flac_header_rejects_invalid_files(data, message):
    with pytest.raises(ValueError, match=message):
        audio_stats.flac_header(data, len(data))


def test_mp3_header_constant_bitrate_uses_file_size():
    data = _make_mp3_cbr(2.0)
    duration, sample_rate = audio_stats.mp3_header(data, len(data))
    assert duration == pytest.approx(2.0)
    assert sample_rate == 44100


def test_mp3_header_skips_id3_tag():
    data = _make_mp3_with_id3(1.0)
    duration, sample_rate = audio_stats.mp3_header(data, len(data))
    assert duration == pytest.approx(1.0)
    assert sample_rate == 44100


def test_mp3_header_uses_xing_frame_count():
    data = _make_mp3_xing(frames=100)
    duration, sample_rate = audio_stats.mp3_header(data, len(data))
    assert duration == pytest.approx(100 * 1152 / 44100)
    assert sample_rate == 44100


@pytest.mark.parametrize(
    ("version", "expected_rate"),
    [(3, 44100), (2, 22050), (0, 11025)],
)
def test_mp3_header_supports_mpeg_versions(version, expected_rate):
    data = _mp3_frame_header(version=version, bitrate_index=8) + bytes(100)
    assert audio_stats.mp3_header(data, len(data))[1] == expected_rate


def test_mp3_header_rejects_invalid_file():
    with pytest.raises(ValueError, match="no MPEG frame"):
        audio_stats.mp3_header(b"not an mp3", 10)


def test_parse_header_is_case_insensitive():
    data = _make_wav()
    assert audio_stats.parse_header("AUDIO.WAV", data, len(data)) == (1.0, 8000)


def test_parse_header_rejects_unsupported_extension():
    with pytest.raises(ValueError, match=r"no parser for \.ogg"):
        audio_stats.parse_header("audio.ogg", b"", 0)


# =============================================================================
# ZIP matching and reading
# =============================================================================


def test_match_members_finds_paths_and_skips_junk():
    archive_data = _zip_bytes(
        {
            "root/audio/a.wav": _make_wav(),
            "root/audio/unlisted.wav": _make_wav(),
            "root/audio/._a.wav": b"resource fork",
            "__MACOSX/root/audio/a.wav": b"resource fork",
        }
    )
    with zipfile.ZipFile(io.BytesIO(archive_data)) as archive:
        found = audio_stats.match_members(archive, {"audio/a.wav"})
    assert list(found) == ["audio/a.wav"]
    assert found["audio/a.wav"].filename == "root/audio/a.wav"


def test_match_members_applies_destination_directory():
    archive_data = _zip_bytes({"audio/a.wav": _make_wav()})
    with zipfile.ZipFile(io.BytesIO(archive_data)) as archive:
        found = audio_stats.match_members(
            archive,
            {"dataset/audio/a.wav"},
            destination_dir="dataset",
        )
    assert list(found) == ["dataset/audio/a.wav"]


@pytest.mark.parametrize("compression", [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED])
def test_member_head_supports_stored_and_deflated(compression):
    wav = _make_wav()
    archive_data = _zip_bytes({"audio.wav": wav}, compression=compression)
    with zipfile.ZipFile(io.BytesIO(archive_data)) as archive:
        info = archive.getinfo("audio.wav")
        head = audio_stats.member_head(_BytesHTTP(archive_data), info)
    assert head[: len(wav)] == wav


def test_member_head_rejects_bad_local_header():
    archive_data = bytearray(_zip_bytes({"audio.wav": _make_wav()}))
    with zipfile.ZipFile(io.BytesIO(archive_data)) as archive:
        info = archive.getinfo("audio.wav")
    archive_data[info.header_offset : info.header_offset + 4] = b"NOPE"

    with pytest.raises(ValueError, match="bad local file header"):
        audio_stats.member_head(_BytesHTTP(bytes(archive_data)), info)


def test_member_head_rejects_unsupported_compression():
    archive_data = _zip_bytes(
        {"audio.wav": _make_wav()},
        compression=zipfile.ZIP_BZIP2,
    )
    with zipfile.ZipFile(io.BytesIO(archive_data)) as archive:
        info = archive.getinfo("audio.wav")
        with pytest.raises(ValueError, match="unsupported zip compression"):
            audio_stats.member_head(_BytesHTTP(archive_data), info)


# =============================================================================
# HTTP range behavior
# =============================================================================


def test_http_file_reads_ranges_and_tracks_usage():
    session = _FakeRangeSession({FAKE_URL: b"0123456789"})
    remote = audio_stats.HTTPFile(FAKE_URL, session)

    assert remote.size == 10
    assert remote.read_at(2, 4) == b"2345"
    assert session.calls[-1][2]["headers"]["Range"] == "bytes=2-5"

    remote.seek(-2, io.SEEK_END)
    assert remote.read() == b"89"
    assert remote.tell() == 10
    assert remote.requests == 2
    assert remote.bytes == 6


def test_http_file_requires_content_length():
    session = _FakeRangeSession({FAKE_URL: b"data"}, include_length=False)
    with pytest.raises(IOError, match="does not report the file size"):
        audio_stats.HTTPFile(FAKE_URL, session)


def test_http_file_rejects_server_that_ignores_range():
    session = _FakeRangeSession({FAKE_URL: b"data"}, ignore_range=True)
    remote = audio_stats.HTTPFile(FAKE_URL, session)
    with pytest.raises(IOError, match="ignored the range request"):
        remote.read_at(0, 2)


@pytest.mark.parametrize(
    "session_kwargs",
    [
        {"short_range": True},
        {"include_content_range": False},
    ],
)
def test_http_file_rejects_invalid_partial_response(session_kwargs):
    """Desired behavior: incomplete or unverified ranges must fail."""
    session = _FakeRangeSession(
        {FAKE_URL: b"0123456789"},
        **session_kwargs,
    )
    remote = audio_stats.HTTPFile(FAKE_URL, session)
    with pytest.raises(IOError):
        remote.read_at(2, 4)


def test_http_file_retries_rate_limit(monkeypatch):
    sleeps = []

    class RateLimitedSession:
        def __init__(self):
            self.attempts = 0

        def request(self, method, url, timeout, **kwargs):
            self.attempts += 1
            if self.attempts == 1:
                return _FakeResponse(
                    429,
                    headers={"Retry-After": "3"},
                    url=url,
                )
            return _FakeResponse(
                200,
                headers={"Content-Length": "4"},
                url=url,
            )

    session = RateLimitedSession()
    monkeypatch.setattr(audio_stats.time, "sleep", sleeps.append)

    remote = audio_stats.HTTPFile(FAKE_URL, session)
    assert remote.size == 4
    assert session.attempts == 2
    assert sleeps == [3.0]


# =============================================================================
# Summary and local mode
# =============================================================================


def test_summarize_uses_first_readable_file_per_track():
    index = {
        "tracks": {
            "a": {
                "audio": ["missing.wav", "x"],
                "audio_backup": ["backup.wav", "x"],
            },
            "b": {
                "audio_one": ["one.wav", "x"],
                "audio_two": ["two.wav", "x"],
            },
            "no_audio": {"beats": ["beats.csv", "x"]},
        }
    }
    stats = audio_stats.summarize(
        index,
        {
            "backup.wav": 2.0,
            "one.wav": 3.0,
            "two.wav": 4.0,
        },
        {
            "backup.wav": 16000,
            "one.wav": 44100,
            "two.wav": 44100,
        },
        {"missing.wav": "file not found"},
    )

    assert stats["n_tracks"] == 3
    assert stats["n_tracks_with_audio"] == 2
    assert stats["n_tracks_counted"] == 2
    assert stats["total_seconds"] == 5.0
    assert stats["all_files_seconds"] == 9.0
    assert stats["n_audio_files"] == 4
    assert stats["n_audio_files_counted"] == 3
    assert stats["sample_rate"] is None
    assert stats["sample_rates"] == {44100: 2, 16000: 1}


def test_summarize_counts_shared_file_once_but_each_track():
    index = {
        "tracks": {
            "a": {"audio": ["shared.wav", "x"]},
            "b": {"audio": ["shared.wav", "x"]},
        }
    }
    stats = audio_stats.summarize(
        index,
        {"shared.wav": 1.2},
        {"shared.wav": 44100},
        {},
    )
    assert stats["n_tracks_counted"] == 2
    assert stats["n_audio_files"] == 1
    assert stats["total_seconds"] == 2.4
    assert stats["all_files_seconds"] == 1.2
    assert stats["sample_rate"] == 44100


def test_summarize_with_nothing_read():
    index = {"tracks": {"a": {"audio": ["missing.wav", "x"]}}}
    stats = audio_stats.summarize(
        index,
        {},
        {},
        {"missing.wav": "file not found"},
    )
    assert stats["n_tracks_counted"] == 0
    assert stats["total_seconds"] == 0
    assert stats["sample_rate"] is None
    assert stats["sample_rates"] == {}


def test_fake_dataset_local_end_to_end(fake_dataset):
    stats = audio_stats.dataset_stats(
        "fake_audio_stats",
        fake_dataset.index,
        {},
        data_home=str(fake_dataset.data_home),
    )
    _assert_fake_summary(stats)


def test_local_durations_respects_sorted_limit(fake_dataset):
    wanted = {
        path
        for paths in audio_stats.track_audio_paths(fake_dataset.index).values()
        for path in paths
    }
    durations, rates, errors, sources = audio_stats.local_durations(
        str(fake_dataset.data_home),
        wanted,
        limit=2,
        verbose=False,
    )
    assert list(durations) == ["audio/a.wav", "audio/b.flac"]
    assert rates == {
        "audio/a.wav": 8000,
        "audio/b.flac": 16000,
    }
    assert errors == {}
    assert len(sources) == 1


def test_local_durations_reports_missing_directory(tmp_path):
    durations, rates, errors, sources = audio_stats.local_durations(
        str(tmp_path / "not-there"),
        {"audio/a.wav"},
        limit=None,
        verbose=False,
    )
    assert durations == {}
    assert rates == {}
    assert errors == {}
    assert "no local copy" in sources[0]


def test_dataset_stats_without_remotes(fake_index):
    stats = audio_stats.dataset_stats(
        "fake_audio_stats",
        fake_index,
        {},
    )
    assert stats["n_tracks"] == 5
    assert stats["n_tracks_counted"] == 0
    assert stats["total_seconds"] == 0
    assert "no remotes" in stats["sources"][0]


# =============================================================================
# Remote ZIP integration and desired failure behavior
# =============================================================================


def test_fake_dataset_remote_zip_end_to_end(fake_dataset, monkeypatch):
    session = _FakeRangeSession({FAKE_URL: fake_dataset.archive})
    monkeypatch.setattr(audio_stats.requests, "Session", lambda: session)

    stats = audio_stats.dataset_stats(
        "fake_audio_stats",
        fake_dataset.index,
        {"audio": _remote()},
        workers=2,
    )

    # This intentionally fails until absent ZIP members are recorded as errors.
    _assert_fake_summary(stats)
    get_calls = [call for call in session.calls if call[0] == "GET"]
    assert get_calls
    assert all("Range" in call[2].get("headers", {}) for call in get_calls)


def test_remote_limit_counts_attempted_files_not_successes(monkeypatch):
    bad_url = "https://example.test/bad.zip"
    good_url = "https://example.test/good.zip"
    session = _FakeRangeSession(
        {
            bad_url: _zip_bytes({"audio/00-bad.wav": b"invalid"}),
            good_url: _zip_bytes({"audio/01-good.wav": _make_wav()}),
        }
    )
    monkeypatch.setattr(audio_stats.requests, "Session", lambda: session)

    durations, rates, errors, sources = audio_stats.remote_durations(
        {
            "bad": _remote("bad.zip", bad_url),
            "good": _remote("good.zip", good_url),
        },
        {"audio/00-bad.wav", "audio/01-good.wav"},
        workers=1,
        limit=1,
        verbose=False,
    )

    # Only the first indexed candidate should have been attempted.
    assert durations == {}
    assert rates == {}
    assert set(errors) == {"audio/00-bad.wav"}
    assert len(sources) == 2


# =============================================================================
# CLI behavior
# =============================================================================


def test_main_local_json(fake_dataset, monkeypatch, capsys):
    dataset = SimpleNamespace(
        index_path=str(fake_dataset.index_path),
        remotes={},
    )
    monkeypatch.setattr(
        audio_stats.mirdata,
        "list_datasets",
        lambda: ["fake_audio_stats"],
    )
    monkeypatch.setattr(
        audio_stats.mirdata,
        "initialize",
        lambda name: dataset,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audio_stats.py",
            "--dataset",
            "fake_audio_stats",
            "--local",
            "--datasets-dir",
            str(fake_dataset.data_home.parent),
            "--json",
        ],
    )

    audio_stats.main()
    result = json.loads(capsys.readouterr().out)
    assert result["name"] == "fake_audio_stats"
    assert result["n_tracks"] == 5
    assert result["n_tracks_counted"] == 3
    assert result["total_seconds"] == 6.5


@pytest.mark.parametrize("limit", ["0", "-1"])
def test_main_rejects_nonpositive_limit(limit, monkeypatch):
    """Desired behavior: zero and negative limits are invalid CLI input."""
    monkeypatch.setattr(audio_stats.mirdata, "list_datasets", lambda: [])
    monkeypatch.setattr(
        sys,
        "argv",
        ["audio_stats.py", "--limit", limit],
    )
    with pytest.raises(SystemExit) as exc:
        audio_stats.main()
    assert exc.value.code == 2


def test_main_json_with_no_selected_datasets(monkeypatch, capsys):
    """Desired behavior: an empty selection produces an empty JSON object."""
    monkeypatch.setattr(
        audio_stats.mirdata,
        "list_datasets",
        lambda: ["fake_audio_stats"],
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audio_stats.py",
            "--exclude",
            "fake_audio_stats",
            "--json",
        ],
    )

    audio_stats.main()
    assert json.loads(capsys.readouterr().out) == {}


def test_main_rejects_unknown_dataset(monkeypatch):
    monkeypatch.setattr(
        audio_stats.mirdata,
        "list_datasets",
        lambda: ["fake_audio_stats"],
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["audio_stats.py", "--dataset", "unknown"],
    )
    with pytest.raises(SystemExit, match="Dataset 'unknown' not found"):
        audio_stats.main()


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0, "0h 00m 00s"),
        (61, "0h 01m 01s"),
        (3661, "1h 01m 01s"),
    ],
)
def test_hms(seconds, expected):
    assert audio_stats.hms(seconds) == expected
