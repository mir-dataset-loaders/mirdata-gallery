"""Tests for scripts/compute_stats.py: both parts, both modes, isolation of failures, CLI."""

import json
import os
from types import SimpleNamespace
from typing import Optional

import numpy as np
import pytest
import requests
from mirdata import annotations as A

import compute_stats
from stats import dataset as stats_dataset
from audio_fakes import FAKE_URL, FakeRangeSession, fake_remote, make_wav, zip_bytes
from stats.histograms import histogram

FILES = {
    "audio/a.wav": make_wav(1.0, 8000),
    "audio/b.wav": make_wav(2.0, 8000),
    "ann/a.txt": b"0.0\n0.5\n1.0\n",  # 120 bpm
    "ann/b.txt": b"0.0\n1.0\n2.0\n",  # 60 bpm
}
INDEX = {
    "tracks": {
        "a": {"audio": ["audio/a.wav", "x"], "beats": ["ann/a.txt", "x"]},
        "b": {"audio": ["audio/b.wav", "x"], "beats": ["ann/b.txt", "x"]},
    }
}


class FileTrack:
    """Like a mirdata Track: reads its beats file from data_home when asked."""

    def __init__(self, data_home, track_id):
        self.path = os.path.join(data_home, INDEX["tracks"][track_id]["beats"][0])

    @property
    def beats(self) -> Optional[A.BeatData]:
        with open(self.path) as f:
            times = [float(line) for line in f if line.strip()]
        return A.BeatData(np.array(times), "s", np.arange(1, len(times) + 1), "bar_index")


@pytest.fixture
def fake_mirdata(tmp_path, monkeypatch):
    """mirdata with one dataset, "fake", whose remote is a zip of FILES; returns the session."""
    index_path = tmp_path / "index.json"
    index_path.write_text(json.dumps(INDEX))

    def initialize(name, data_home):
        return SimpleNamespace(
            index_path=str(index_path),
            remotes={"all": fake_remote("all.zip", FAKE_URL)},
            _track_class=FileTrack,
            track_ids=list(INDEX["tracks"]),
            track=lambda track_id: FileTrack(data_home, track_id),
        )

    session = FakeRangeSession({FAKE_URL: zip_bytes(FILES)})
    monkeypatch.setattr(compute_stats.mirdata, "list_datasets", lambda: ["fake", "other"])
    monkeypatch.setattr(compute_stats.mirdata, "initialize", initialize)
    monkeypatch.setattr(requests, "Session", lambda: session)
    return session


def local_copy(tmp_path):
    for path, data in FILES.items():
        (tmp_path / "datasets" / "fake" / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "datasets" / "fake" / path).write_bytes(data)
    return str(tmp_path / "datasets")


def run_json(capsys, *argv):
    compute_stats.main(list(argv) + ["--json"])
    return json.loads(capsys.readouterr().out)


# ------------------------------------------------------------------ both parts


def test_local_both_parts(tmp_path, fake_mirdata, capsys):
    result = run_json(capsys, "--dataset", "fake", "--local", "--datasets-dir", local_copy(tmp_path))
    fake = result["fake"]
    assert sorted(fake) == ["annotations", "audio", "name"]
    assert fake["audio"]["n_tracks_counted"] == 2
    assert fake["audio"]["total_seconds"] == 3.0
    assert fake["audio"]["sample_rate"] == 8000
    assert fake["annotations"]["annotations"]["beats"]["tempo"] == histogram([120.0, 60.0], "bpm")
    assert "name" not in fake["audio"] and "name" not in fake["annotations"]
    assert fake_mirdata.calls == []  # local mode never touches the network


def test_remote_both_parts_is_the_default(tmp_path, fake_mirdata, capsys):
    fetch_dir = tmp_path / "kept"
    result = run_json(capsys, "--dataset", "fake", "--fetch-dir", str(fetch_dir))
    fake = result["fake"]
    assert fake["audio"]["total_seconds"] == 3.0  # read by range from the zip
    assert fake["annotations"]["annotations"]["beats"]["n_tracks"] == 2
    assert fake["annotations"]["missing_files"] == {}
    assert (fetch_dir / "fake" / "ann" / "a.txt").exists()  # --fetch-dir keeps the files
    assert not (fetch_dir / "fake" / "audio").exists()  # the audio is never downloaded


def test_remote_fetch_folder_is_temporary_by_default(tmp_path, fake_mirdata, capsys, monkeypatch):
    made = []
    real = compute_stats.tempfile.TemporaryDirectory

    def tracking(*args, **kwargs):
        made.append(real(*args, **kwargs))
        return made[-1]

    monkeypatch.setattr(compute_stats.tempfile, "TemporaryDirectory", tracking)
    run_json(capsys, "--dataset", "fake")
    assert made and not os.path.exists(made[0].name)


@pytest.mark.parametrize("part", ["audio", "annotations"])
def test_only_one_part(tmp_path, fake_mirdata, capsys, part):
    result = run_json(capsys, "--dataset", "fake", "--only", part, "--local", "--datasets-dir", local_copy(tmp_path))
    assert sorted(result["fake"]) == sorted(["name", part])


# ---------------------------------------------------------- failures stay local


def test_a_failing_part_does_not_stop_the_other(tmp_path, fake_mirdata, capsys, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("audio exploded")

    monkeypatch.setattr(stats_dataset.audio, "dataset_stats", broken)
    result = run_json(capsys, "--dataset", "fake", "--local", "--datasets-dir", local_copy(tmp_path))
    assert result["fake"]["audio"] == {"status": "error", "error": "RuntimeError: audio exploded"}
    assert result["fake"]["annotations"]["annotations"]["beats"]["n_tracks"] == 2


def test_missing_local_copy_is_checked_once_for_the_dataset(tmp_path, fake_mirdata, capsys):
    result = run_json(capsys, "--dataset", "fake", "--local", "--datasets-dir", str(tmp_path / "none"))
    assert result["fake"] == {"name": "fake", "error": f"no local copy at {tmp_path / 'none' / 'fake'}"}


def test_loader_that_cannot_be_initialized(fake_mirdata, capsys, monkeypatch):
    def initialize(name, data_home):
        raise ImportError("missing optional dependency")

    monkeypatch.setattr(compute_stats.mirdata, "initialize", initialize)
    result = run_json(capsys, "--dataset", "fake")
    assert result["fake"] == {"name": "fake", "error": "ImportError: missing optional dependency"}


# ------------------------------------------------------------------- arguments


def test_empty_selection_gives_empty_json(fake_mirdata, capsys):
    assert run_json(capsys, "--exclude", "fake,other") == {}


def test_rejects_unknown_dataset(fake_mirdata):
    with pytest.raises(SystemExit, match="Dataset 'unknown' not found"):
        compute_stats.main(["--dataset", "unknown"])


@pytest.mark.parametrize("argv", [["--limit", "0"], ["--limit", "-1"], ["--only", "lyrics"]])
def test_rejects_bad_arguments(argv, fake_mirdata):
    with pytest.raises(SystemExit) as exc:
        compute_stats.main(argv)
    assert exc.value.code == 2


# -------------------------------------------------------------------- printing


def test_printed_output_has_both_parts(tmp_path, fake_mirdata, capsys):
    compute_stats.main(["--dataset", "fake", "--local", "--datasets-dir", local_copy(tmp_path), "--limit", "1"])
    out = capsys.readouterr().out
    assert out.startswith("fake\n  [audio]\n")
    assert "  [annotations]\n" in out
    assert "total duration:         1 s" in out
    assert "(only the first 1 audio files were read)" in out
    assert "beats (BeatData; 1 tracks)" in out
    assert "(only the first 1 tracks were read)" in out


def test_printed_table_after_several_datasets(tmp_path, fake_mirdata, capsys, monkeypatch):
    def initialize(name, data_home):
        if name == "other":
            raise ImportError("missing optional dependency")
        return fake_mirdata_initialize(name, data_home)

    fake_mirdata_initialize = compute_stats.mirdata.initialize
    monkeypatch.setattr(compute_stats.mirdata, "initialize", initialize)
    compute_stats.main(["--local", "--datasets-dir", local_copy(tmp_path)])
    table = capsys.readouterr().out.split("\ndataset")[1]
    assert "fake" in table and "8000" in table and "0h 00m 03s" in table
    assert "other" in table and "no local copy" in table  # checked before initializing


def test_print_annotations_shows_skips_and_errors(capsys):
    stats = {
        "status": "incomplete",
        "problems": [],
        "sources": ["  local                  /data/fake"],
        "missing_files": {},
        "n_tracks": 2,
        "n_tracks_loaded": 2,
        "tracks_with": {"BeatData": 2},
        "annotations": {"beats": {"type": "BeatData", "n_tracks": 2, "n_annotations": 3, "beats_per_bar": {4: 2}}},
        "skipped": {"tempo": "not a mirdata TempoData object (got str)"},
        "annotation_errors": {"chords": {"n_tracks": 2, "examples": {"0": "ValueError: keys ['f:minor']"}}},
        "errors": {},
    }
    compute_stats.print_annotations(stats, limit=None)
    out = capsys.readouterr().out
    assert "beats (BeatData; 2 tracks, 3 annotations)" in out
    assert "beats_per_bar              4: 2" in out
    assert "skipped tempo: not a mirdata TempoData object (got str)" in out
    assert "chords failed on 2 tracks, e.g.\n    0: ValueError: keys ['f:minor']" in out



# ------------------------------------------------------------ status, limits


def test_status_is_in_the_json(tmp_path, fake_mirdata, capsys):
    result = run_json(capsys, "--dataset", "fake", "--local", "--datasets-dir", local_copy(tmp_path))
    assert result["fake"]["audio"]["status"] == "ok"
    assert result["fake"]["annotations"]["status"] == "ok"
    assert result["fake"]["audio"]["problems"] == []


def test_max_mb_limits_the_annotations_not_the_audio_headers(fake_mirdata, capsys, monkeypatch):
    compute_stats.main(["--dataset", "fake", "--max-mb", "1"])
    out = capsys.readouterr().out
    assert out.count("status:                 ok") == 2  # the fake zip is tiny: within 1 MB

    real_budget = stats_dataset.Budget
    monkeypatch.setattr(stats_dataset, "Budget", lambda max_mb, max_minutes: real_budget(1e-6, max_minutes))
    compute_stats.main(["--dataset", "fake"])
    out = capsys.readouterr().out
    assert out.count("status:                 needs_local") == 1
    assert "Run these locally (python scripts/compute_stats.py --local --dataset <name>):" in out
    assert "fake                         annotations  remote limit:" in out
    assert "fake                         audio        remote limit:" not in out


def test_one_budget_per_dataset(fake_mirdata, capsys, monkeypatch):
    made = []
    real_budget = stats_dataset.Budget

    def counting_budget(max_mb, max_minutes):
        made.append(real_budget(max_mb, max_minutes))
        return made[-1]

    monkeypatch.setattr(stats_dataset, "Budget", counting_budget)
    compute_stats.main(["--dataset", "fake"])
    capsys.readouterr()
    assert len(made) == 1  # shared by audio and annotations
    assert made[0].bytes > 0  # charged by the annotation download


def test_local_runs_have_no_budget(tmp_path, fake_mirdata, capsys, monkeypatch):
    def no_budget(*args):
        raise AssertionError("local mode must not make a budget")

    monkeypatch.setattr(stats_dataset, "Budget", no_budget)
    result = run_json(capsys, "--dataset", "fake", "--local", "--datasets-dir", local_copy(tmp_path))
    assert result["fake"]["audio"]["status"] == "ok"


def test_summary_groups_needs_local_incomplete_and_failed(capsys):
    results = {
        "a": {"name": "a", "audio": {"status": "ok", "problems": []}},
        "b": {"name": "b", "audio": {"status": "needs_local", "problems": ["no remotes: x"]}},
        "c": {"name": "c", "annotations": {"status": "incomplete", "problems": []}},
        "d": {"name": "d", "error": "ImportError: y"},
        "e": {"name": "e", "audio": {"status": "error", "error": "RuntimeError: z"}},
    }
    compute_stats.print_to_do(results, "python scripts/compute_stats.py --local --dataset <name>")
    out = capsys.readouterr().out
    assert "Run these locally (python scripts/compute_stats.py --local --dataset <name>):" in out and "b                            audio        no remotes: x" in out
    assert "Incomplete" in out and "c                            annotations  see its errors" in out
    assert "Failed:" in out and "ImportError: y" in out and "RuntimeError: z" in out
    assert "\n  a " not in out


def test_nothing_to_do_prints_nothing(capsys):
    compute_stats.print_to_do({"a": {"name": "a", "audio": {"status": "ok", "problems": []}}}, "cmd")
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("flag", ["--max-mb", "--max-minutes"])
def test_limits_must_be_positive(flag, fake_mirdata):
    with pytest.raises(SystemExit) as exc:
        compute_stats.main([flag, "0"])
    assert exc.value.code == 2


def test_index_is_loaded_once_for_both_parts(tmp_path, fake_mirdata, capsys, monkeypatch):
    calls = []
    real = stats_dataset.load_index

    def counting(ds):
        calls.append(ds)
        return real(ds)

    monkeypatch.setattr(stats_dataset, "load_index", counting)
    result = run_json(capsys, "--dataset", "fake")  # remote: both parts need the index
    assert result["fake"]["audio"]["status"] == "ok"
    assert result["fake"]["annotations"]["status"] == "ok"
    assert len(calls) == 1


def test_index_error_reaches_both_parts(fake_mirdata, capsys, monkeypatch):
    def broken(ds):
        raise OSError("index 404")

    monkeypatch.setattr(stats_dataset, "load_index", broken)
    result = run_json(capsys, "--dataset", "fake")
    assert result["fake"]["audio"] == {"status": "error", "error": "OSError: index 404"}
    assert result["fake"]["annotations"] == {"status": "error", "error": "OSError: index 404"}
