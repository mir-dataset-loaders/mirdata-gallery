"""Tests for scripts/stats/remote_zip.py: zip member matching and HTTP range reading."""

import io
import zipfile

import pytest

from stats import remote_zip
from stats.audio import headers as audio_headers
from audio_fakes import FAKE_URL, BytesHTTP, FakeRangeSession, FakeResponse, make_wav, zip_bytes


# =============================================================================
# ZIP matching and reading
# =============================================================================


def test_match_members_finds_paths_and_skips_junk():
    archive_data = zip_bytes(
        {
            "root/audio/a.wav": make_wav(),
            "root/audio/unlisted.wav": make_wav(),
            "root/audio/._a.wav": b"resource fork",
            "__MACOSX/root/audio/a.wav": b"resource fork",
        }
    )
    with zipfile.ZipFile(io.BytesIO(archive_data)) as archive:
        found = remote_zip.match_members(archive, {"audio/a.wav"})
    assert list(found) == ["audio/a.wav"]
    assert found["audio/a.wav"].filename == "root/audio/a.wav"


def test_match_members_applies_destination_directory():
    archive_data = zip_bytes({"audio/a.wav": make_wav()})
    with zipfile.ZipFile(io.BytesIO(archive_data)) as archive:
        found = remote_zip.match_members(
            archive,
            {"dataset/audio/a.wav"},
            destination_dir="dataset",
        )
    assert list(found) == ["dataset/audio/a.wav"]


@pytest.mark.parametrize("compression", [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED])
def test_member_head_supports_stored_and_deflated(compression):
    wav = make_wav()
    archive_data = zip_bytes({"audio.wav": wav}, compression=compression)
    with zipfile.ZipFile(io.BytesIO(archive_data)) as archive:
        info = archive.getinfo("audio.wav")
        head = remote_zip.member_head(BytesHTTP(archive_data), info, audio_headers.HEADER_BYTES)
    assert head[: len(wav)] == wav


def test_member_head_rejects_bad_local_header():
    archive_data = bytearray(zip_bytes({"audio.wav": make_wav()}))
    with zipfile.ZipFile(io.BytesIO(archive_data)) as archive:
        info = archive.getinfo("audio.wav")
    archive_data[info.header_offset : info.header_offset + 4] = b"NOPE"

    with pytest.raises(ValueError, match="bad local file header"):
        remote_zip.member_head(BytesHTTP(bytes(archive_data)), info, audio_headers.HEADER_BYTES)


def test_member_head_rejects_unsupported_compression():
    archive_data = zip_bytes(
        {"audio.wav": make_wav()},
        compression=zipfile.ZIP_BZIP2,
    )
    with zipfile.ZipFile(io.BytesIO(archive_data)) as archive:
        info = archive.getinfo("audio.wav")
        with pytest.raises(ValueError, match="unsupported zip compression"):
            remote_zip.member_head(BytesHTTP(archive_data), info, audio_headers.HEADER_BYTES)


# =============================================================================
# HTTP range behavior
# =============================================================================


def test_http_file_reads_ranges_and_tracks_usage():
    session = FakeRangeSession({FAKE_URL: b"0123456789"})
    remote = remote_zip.HTTPFile(FAKE_URL, session)

    assert remote.size == 10
    assert remote.read_at(2, 4) == b"2345"
    assert session.calls[-1][2]["headers"]["Range"] == "bytes=2-5"

    remote.seek(-2, io.SEEK_END)
    assert remote.read() == b"89"
    assert remote.tell() == 10
    assert remote.requests == 2
    assert remote.bytes == 6


def test_http_file_requires_content_length():
    session = FakeRangeSession({FAKE_URL: b"data"}, include_length=False)
    with pytest.raises(IOError, match="does not report the file size"):
        remote_zip.HTTPFile(FAKE_URL, session)


def test_http_file_rejects_server_that_ignores_range():
    session = FakeRangeSession({FAKE_URL: b"data"}, ignore_range=True)
    remote = remote_zip.HTTPFile(FAKE_URL, session)
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
    session = FakeRangeSession(
        {FAKE_URL: b"0123456789"},
        **session_kwargs,
    )
    remote = remote_zip.HTTPFile(FAKE_URL, session)
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
                return FakeResponse(
                    429,
                    headers={"Retry-After": "3"},
                    url=url,
                )
            return FakeResponse(
                200,
                headers={"Content-Length": "4"},
                url=url,
            )

    session = RateLimitedSession()
    monkeypatch.setattr(remote_zip.time, "sleep", sleeps.append)

    remote = remote_zip.HTTPFile(FAKE_URL, session)
    assert remote.size == 4
    assert session.attempts == 2
    assert sleeps == [3.0]


@pytest.mark.parametrize("compression", [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED])
def test_member_bytes_reads_whole_member(compression):
    payload = b"0.5;1\n" * 5000  # bigger than the 4 KB header slack
    archive = zip_bytes({"beats/a.csv": payload}, compression=compression)
    info = zipfile.ZipFile(io.BytesIO(archive)).getinfo("beats/a.csv")
    assert remote_zip.member_bytes(BytesHTTP(archive), info) == payload


def test_member_bytes_rejects_corrupt_data():
    archive = bytearray(zip_bytes({"a.csv": b"hello world"}, compression=zipfile.ZIP_STORED))
    info = zipfile.ZipFile(io.BytesIO(bytes(archive))).getinfo("a.csv")
    data_start = archive.index(b"hello world")
    archive[data_start] ^= 0xFF
    with pytest.raises(ValueError, match="CRC mismatch"):
        remote_zip.member_bytes(BytesHTTP(bytes(archive)), info)


def test_member_bytes_rejects_bad_local_header():
    archive = zip_bytes({"a.csv": b"x"})
    info = zipfile.ZipFile(io.BytesIO(archive)).getinfo("a.csv")
    with pytest.raises(ValueError, match="bad local file header"):
        remote_zip.member_bytes(BytesHTTP(b"\0" * len(archive)), info)


def test_match_members_strips_unpack_directories():
    archive = zip_bytes(
        {
            "Repo-master/beats/a.beats": b"1",
            "Repo-master/other/b.beats": b"2",
            "Data/Truth/c.bpm": b"3",
        }
    )
    zf = zipfile.ZipFile(io.BytesIO(archive))
    found = remote_zip.match_members(
        zf,
        {"ann/beats/a.beats", "ann/c.bpm"},
        destination_dir="ann",
        unpack_directories=["Repo-master", "Data/Truth/"],
    )
    assert set(found) == {"ann/beats/a.beats", "ann/c.bpm"}
    # without the unpack directories the wrapper folder blocks the match
    assert remote_zip.match_members(zf, {"ann/beats/a.beats"}, destination_dir="ann") == {}


def test_http_file_checks_and_charges_the_budget():
    from stats.common import Budget, RemoteLimit

    budget = Budget(max_mb=0.000010)  # 10 bytes
    session = FakeRangeSession({FAKE_URL: bytes(range(32))})
    http = remote_zip.HTTPFile(FAKE_URL, session, budget)
    assert http.read_at(0, 8) == bytes(range(8))
    assert budget.bytes == 8
    with pytest.raises(RemoteLimit):
        http.read_at(8, 8)
    assert len([call for call in session.calls if call[0] == "GET"]) == 1  # refused before asking
