"""Tests for scripts/stats/audio: index handling, counting, local/remote modes."""

import json
import zipfile
from types import SimpleNamespace

import pytest

from stats import common
from stats.audio import dataset_stats, summary
from stats.audio import sources as audio_sources
from audio_fakes import FAKE_URL, FakeRangeSession, FakeResponse, fake_remote, make_wav, zip_bytes

EXPECTED_SUMMARY = {
    "n_tracks": 5,
    "n_tracks_with_audio": 4,
    "n_tracks_counted": 3,
    "total_seconds": 6.5,
    "duration_histogram": {"unit": "s", "edges": [1, 2, 3, 4], "counts": [1, 1, 1]},
    "n_audio_files": 6,
    "n_audio_files_counted": 4,
    "all_files_seconds": 10.5,
    "sample_rate": None,
    "sample_rates": {8000: 2, 16000: 1, 44100: 1},
}


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
    assert summary.track_audio_paths(fake_index) == {
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
    assert summary.track_audio_paths(index) == {"case": ["audio/a.wav"]}


def test_load_index_uses_existing_file(tmp_path, monkeypatch, fake_index):
    index_path = tmp_path / "index.json"
    index_path.write_text(json.dumps(fake_index), encoding="utf-8")
    dataset = SimpleNamespace(index_path=str(index_path))

    def unexpected_download(*args, **kwargs):
        raise AssertionError("existing index should not be downloaded")

    monkeypatch.setattr(
        common.download_utils,
        "download_from_remote",
        unexpected_download,
    )
    assert common.load_index(dataset) == fake_index


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
        common.download_utils,
        "download_from_remote",
        download,
    )
    assert common.load_index(dataset) == fake_index


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
        common.download_utils,
        "download_from_remote",
        lambda *args: str(archive_path),
    )

    def unzip(path, cleanup):
        unzip_calls.append((path, cleanup))
        with zipfile.ZipFile(path) as archive:
            archive.extractall(tmp_path)

    monkeypatch.setattr(common.download_utils, "unzip", unzip)

    assert common.load_index(dataset) == fake_index
    assert unzip_calls == [(str(archive_path), False)]


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
    stats = summary.summarize(
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
    stats = summary.summarize(
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
    stats = summary.summarize(
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
    stats = dataset_stats(
        "fake_audio_stats",
        fake_dataset.index,
        {},
        data_home=str(fake_dataset.data_home),
    )
    _assert_fake_summary(stats)


def test_local_durations_respects_sorted_limit(fake_dataset):
    wanted = {
        path
        for paths in summary.track_audio_paths(fake_dataset.index).values()
        for path in paths
    }
    durations, rates, errors, sources, problems = audio_sources.local_durations(
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


def test_local_durations_without_local_copy_is_an_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="no local copy"):
        audio_sources.local_durations(str(tmp_path / "not-there"), {"audio/a.wav"}, limit=None, verbose=False)


def test_dataset_stats_without_remotes(fake_index):
    stats = dataset_stats(
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
    session = FakeRangeSession({FAKE_URL: fake_dataset.archive})
    monkeypatch.setattr(audio_sources.requests, "Session", lambda: session)

    stats = dataset_stats(
        "fake_audio_stats",
        fake_dataset.index,
        {"audio": fake_remote()},
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
    session = FakeRangeSession(
        {
            bad_url: zip_bytes({"audio/00-bad.wav": b"invalid"}),
            good_url: zip_bytes({"audio/01-good.wav": make_wav()}),
        }
    )
    monkeypatch.setattr(audio_sources.requests, "Session", lambda: session)

    durations, rates, errors, sources, problems = audio_sources.remote_durations(
        {
            "bad": fake_remote("bad.zip", bad_url),
            "good": fake_remote("good.zip", good_url),
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
# Helpers
# =============================================================================


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0, "0h 00m 00s"),
        (61, "0h 01m 01s"),
        (3661, "1h 01m 01s"),
    ],
)
def test_hms(seconds, expected):
    assert common.hms(seconds) == expected


# =============================================================================
# Remote problems and status
# =============================================================================


def read_remote(remotes, wanted, session, monkeypatch, budget=None, limit=None):
    monkeypatch.setattr(audio_sources.requests, "Session", lambda: session)
    return audio_sources.remote_durations(remotes, wanted, workers=1, limit=limit, verbose=False, budget=budget)


def test_complete_remote_read_has_no_problems(monkeypatch):
    session = FakeRangeSession({FAKE_URL: zip_bytes({"audio/a.wav": make_wav()})})
    durations, rates, errors, sources, problems = read_remote(
        {"all": fake_remote()}, {"audio/a.wav"}, session, monkeypatch
    )
    assert list(durations) == ["audio/a.wav"]
    assert errors == {} and problems == []


def test_no_remotes_is_a_problem():
    *_, problems = audio_sources.remote_durations({}, {"audio/a.wav"}, 1, None, False)
    assert problems == ["no remotes: the audio has to be downloaded manually"]


def test_tar_remote_is_named_as_not_readable(monkeypatch):
    session = FakeRangeSession({})
    *_, problems = read_remote(
        {"audio": fake_remote("audio.tar.gz", "https://example.test/audio.tar.gz")},
        {"audio/a.wav", "audio/b.wav"},
        session,
        monkeypatch,
    )
    assert problems == [
        "2 audio files not found in the readable remotes; "
        "not readable: audio.tar.gz cannot be read remotely (not a zip)"
    ]
    assert session.calls == []


def test_remote_without_access_is_named(monkeypatch):
    class Forbidden(FakeRangeSession):
        def request(self, method, url, timeout, **kwargs):
            return FakeResponse(403, url=url)

    *_, problems = read_remote({"all": fake_remote()}, {"audio/a.wav"}, Forbidden({}), monkeypatch)
    assert "not readable: fake_audio.zip: HTTPError: HTTP 403" in problems[0]


def test_budget_stops_the_remote_read(monkeypatch):
    from stats.common import Budget

    files = {f"audio/{i}.wav": make_wav() for i in range(4)}  # 16 KB each, stored uncompressed
    session = FakeRangeSession({FAKE_URL: zip_bytes(files, compression=zipfile.ZIP_STORED)})
    durations, rates, errors, sources, problems = read_remote(
        {"all": fake_remote()}, set(files), session, monkeypatch, budget=Budget(max_mb=0.04)
    )
    assert problems and problems[0].startswith("remote limit: needs more than the 0.04 MB remote limit")
    assert len(problems) == 1  # the limit explains the unread files; no second reason
    assert len(durations) < 4
    assert not any("RemoteLimit" in e for e in errors.values())  # not one error per file


def test_unparsable_file_is_incomplete_not_needs_local(monkeypatch):
    session = FakeRangeSession({FAKE_URL: zip_bytes({"audio/bad.wav": b"not audio"})})
    stats = dataset_stats_remote({"audio": ["audio/bad.wav", "x"]}, session, monkeypatch)
    assert stats["status"] == "incomplete"
    assert stats["problems"] == []


def test_status_needs_local_with_its_reason(monkeypatch):
    stats = dataset_stats("fake", {"tracks": {"a": {"audio": ["audio/a.wav", "x"]}}}, {})
    assert stats["status"] == "needs_local"
    assert stats["problems"] == ["no remotes: the audio has to be downloaded manually"]


def dataset_stats_remote(track, session, monkeypatch):
    monkeypatch.setattr(audio_sources.requests, "Session", lambda: session)
    return dataset_stats("fake", {"tracks": {"a": track}}, {"all": fake_remote()}, workers=1)
