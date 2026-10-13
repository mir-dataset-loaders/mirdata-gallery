"""Tests for the stats in scripts/generate_cards.py: when they are computed, kept or replaced."""

import os
from types import SimpleNamespace

import pytest
import yaml

import generate_cards
from stats import to_card

FP = "fingerprint00001"


def stats_with(status, fingerprint=FP, mode="remote"):
    part = {"status": status, "problems": ["why"] if status == "needs_local" else []}
    return {
        "computed": {"mode": mode, "index": fingerprint, "date": "2026-10-12"},
        "audio": dict(part),
        "annotations": dict(part),
    }


@pytest.fixture
def fake_compute(monkeypatch):
    """stats.dataset.compute replaced by a recorder returning a result of the given status."""
    calls = []
    state = {"status": "ok"}

    def compute(name, data_home, local=False, **kwargs):
        calls.append({"name": name, "data_home": data_home, "local": local, **kwargs})
        part = {"status": state["status"], "problems": ["why"] if state["status"] == "needs_local" else []}
        return {"name": name, "audio": dict(part), "annotations": dict(part)}

    monkeypatch.setattr(generate_cards.stats_dataset, "compute", compute)
    monkeypatch.setattr(generate_cards.to_card, "index_fingerprint", lambda ds: FP)
    return SimpleNamespace(calls=calls, state=state)


def options(tmp_path, **changes):
    base = {
        "local": False,
        "datasets_dir": str(tmp_path / "mir_datasets"),
        "fetch_root": str(tmp_path / "fetch"),
        "max_mb": 500,
        "max_minutes": 10,
        "force": False,
    }
    return {**base, **changes}


DS = SimpleNamespace(name="fake")


# ------------------------------------------------------------ the decision


def test_no_stats_keeps_old_ones(fake_compute):
    old = stats_with("ok")
    assert generate_cards.card_stats(DS, old, None) == (old, "kept")
    assert generate_cards.card_stats(DS, None, None) == (None, "none")
    assert fake_compute.calls == []


def test_card_without_stats_gets_them(tmp_path, fake_compute):
    stats, status = generate_cards.card_stats(DS, None, options(tmp_path))
    assert status == "new"
    assert stats["computed"]["index"] == FP and stats["computed"]["mode"] == "remote"
    assert fake_compute.calls[0]["data_home"] == str(tmp_path / "fetch" / "fake")
    assert fake_compute.calls[0]["max_mb"] == 500


def test_current_stats_are_kept_without_computing(tmp_path, fake_compute):
    old = stats_with("needs_local")
    assert generate_cards.card_stats(DS, old, options(tmp_path)) == (old, "kept")
    assert fake_compute.calls == []


def test_new_index_recomputes_and_replaces_even_better_old_stats(tmp_path, fake_compute):
    old = stats_with("ok", fingerprint="old-index-000000", mode="local")
    fake_compute.state["status"] = "needs_local"
    stats, status = generate_cards.card_stats(DS, old, options(tmp_path))
    assert status == "new" and stats["audio"]["status"] == "needs_local"


def test_force_recomputes(tmp_path, fake_compute):
    stats, status = generate_cards.card_stats(DS, stats_with("needs_local"), options(tmp_path, force=True))
    assert status == "new" and stats["audio"]["status"] == "ok"


def test_local_run_replaces_remote_needs_local(tmp_path, fake_compute):
    (tmp_path / "mir_datasets" / "fake").mkdir(parents=True)
    stats, status = generate_cards.card_stats(DS, stats_with("needs_local"), options(tmp_path, local=True))
    assert status == "new"
    assert stats["computed"]["mode"] == "local"
    assert fake_compute.calls[0]["local"] is True
    assert fake_compute.calls[0]["data_home"] == str(tmp_path / "mir_datasets" / "fake")


def test_local_run_without_local_copy_keeps_old(tmp_path, fake_compute):
    old = stats_with("needs_local")
    assert generate_cards.card_stats(DS, old, options(tmp_path, local=True)) == (old, "kept (no local copy)")
    assert fake_compute.calls == []


def test_worse_result_never_replaces_better_current_one(tmp_path, fake_compute):
    old = stats_with("ok", mode="local")
    fake_compute.state["status"] = "needs_local"
    stats, status = generate_cards.card_stats(DS, old, options(tmp_path, force=True))
    assert stats is old
    assert status == "kept (more complete than the new run)"


@pytest.mark.parametrize(
    ("stats", "expected"),
    [
        (None, -1),
        ({"computed": {}, "error": "ImportError: x"}, 0),
        (stats_with("ok"), 3),
        ({**stats_with("ok"), "annotations": {"status": "incomplete", "problems": []}}, 2),
    ],
)
def test_rank_is_the_worst_part(stats, expected):
    assert to_card.rank(stats) == expected


# ------------------------------------------------------------ the whole run


def test_generate_writes_stats_into_the_card_and_lists_needs_local(tmp_path, fake_compute, monkeypatch, capsys):
    class Track:
        pass

    def initialize(name, data_home=None):
        return SimpleNamespace(name=name, _track_class=Track, remotes={}, bibtex="@misc{x}")

    monkeypatch.setattr(generate_cards.mirdata, "initialize", initialize)
    monkeypatch.setattr(generate_cards.llm, "loader_docstring", lambda name: None)
    fake_compute.state["status"] = "needs_local"
    out_dir = tmp_path / "cards"

    generate_cards.generate(["fake"], str(out_dir), summarize=False, stats_options=options(tmp_path))
    card = yaml.safe_load((out_dir / "fake.yaml").read_text())
    assert list(card) == ["name", "license", "annotations", "bibtex", "summary", "stats"]
    assert card["stats"]["audio"]["status"] == "needs_local"
    out = capsys.readouterr().out
    assert "stats: new, audio needs_local, annotations needs_local" in out
    to_do = out.split("Run these locally (python scripts/generate_cards.py --local --dataset <name>):")[1]
    assert "fake                         audio        why" in to_do

    # a second run keeps them: same index, nothing computed
    generate_cards.generate(["fake"], str(out_dir), summarize=False, stats_options=options(tmp_path))
    assert len(fake_compute.calls) == 1
    assert "stats: kept" in capsys.readouterr().out

    # --no-stats keeps them too, and never computes
    generate_cards.generate(["fake"], str(out_dir), summarize=False, stats_options=None)
    assert len(fake_compute.calls) == 1
    assert yaml.safe_load((out_dir / "fake.yaml").read_text())["stats"] == card["stats"]


def test_main_passes_the_stats_flags(monkeypatch, tmp_path):
    seen = {}
    monkeypatch.setattr(generate_cards.mirdata, "list_datasets", lambda: ["fake"])
    monkeypatch.setattr(generate_cards, "generate", lambda names, out, **kw: seen.update(kw, names=names))
    monkeypatch.setattr(
        "sys.argv",
        ["generate_cards.py", "--dataset", "fake", "--local", "--force-stats", "--max-mb", "50",
         "--datasets-dir", str(tmp_path)],
    )
    generate_cards.main()
    opts = seen["stats_options"]
    assert opts["local"] and opts["force"] and opts["max_mb"] == 50 and opts["datasets_dir"] == str(tmp_path)
    assert not os.path.exists(opts["fetch_root"])  # temporary, deleted after the run

    monkeypatch.setattr("sys.argv", ["generate_cards.py", "--dataset", "fake", "--no-stats"])
    generate_cards.main()
    assert seen["stats_options"] is None
