"""Tests for scripts/audio_stats.py: index handling, counting, local/remote modes, CLI."""

import json
import sys
import zipfile
from types import SimpleNamespace

import pytest

import audio_stats
from audio_fakes import FAKE_URL, FakeRangeSession, fake_remote, make_wav, zip_bytes

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
    session = FakeRangeSession({FAKE_URL: fake_dataset.archive})
    monkeypatch.setattr(audio_stats.requests, "Session", lambda: session)

    stats = audio_stats.dataset_stats(
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
    monkeypatch.setattr(audio_stats.requests, "Session", lambda: session)

    durations, rates, errors, sources = audio_stats.remote_durations(
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
