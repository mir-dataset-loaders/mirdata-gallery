"""generate_cards.py on the fake dataset: the card it writes, and when its stats are recomputed or kept.

The rules (scripts/scripts_structure.md, "Stats in the cards"):
  - stats are computed when the card has none, the index changed, or with
    --force-stats or --local; otherwise the card keeps its stats;
  - for the same index, the more complete stats win (ok, incomplete,
    needs_local, error, judged by the worst part).
Each test runs the command line as a user would, with --no-summary (no LLM).
"""

import sys
import tempfile

import pytest

import card_utils
import fake_dataset
import generate_cards
from conftest import files_under
from fake_dataset import RESOURCES
from test_cards_schema import validate_card

LOCAL_DIR = f"{RESOURCES}/mir_datasets"  # holds fake_dataset/


@pytest.fixture
def run(fake_remotes, tmp_path, monkeypatch, capsys):
    """run(*flags): generate_cards.py for fake_dataset into tmp_path/cards; returns the card.

    The test fails unless the run reports the card as written ([OK]): a run that
    fails leaves the previous card on disk, which would pass for "stats kept".
    run.out holds what the run printed.
    """
    cards = str(tmp_path / "cards")

    def run(*flags):
        argv = ["generate_cards.py", "--dataset", "fake_dataset", "--output", cards, "--no-summary"]
        monkeypatch.setattr(sys, "argv", [*argv, *flags])
        fake_remotes.requests.clear()
        generate_cards.main()
        run.out = capsys.readouterr().out
        assert "[OK]    fake_dataset" in run.out, run.out
        return card_utils.read_card(card_utils.card_path(cards, "fake_dataset"))

    return run


def change_index(monkeypatch):
    """mirdata publishes a new index for the dataset, so a new checksum."""
    monkeypatch.setattr(fake_dataset.INDEXES["1.0"].remote, "checksum", "0123456789abcdef0123456789abcdef")


def test_new_card_has_fields_and_stats(run):
    card = run()
    assert card["name"] == "fake_dataset"
    assert card["license"] == fake_dataset.LICENSE_INFO
    assert card["annotations"] == ["BeatData", "ChordData"]
    stats = card["stats"]
    assert stats["computed"]["mode"] == "remote"
    assert stats["audio"] == {"status": "ok", "problems": [], "n_tracks": 3, "n_audio_files": 3}
    assert stats["annotations"]["status"] == "ok"
    assert stats["annotations"]["tracks_with"] == {"BeatData": 3, "ChordData": 2}


def test_new_card_passes_the_schema(run):
    assert validate_card(run(), "fake_dataset.yaml") == []


def test_stats_kept_when_index_is_unchanged(run, fake_remotes):
    first = run()
    second = run()
    assert fake_remotes.requests == []
    assert second["stats"] == first["stats"]


def test_stats_recomputed_when_index_changes(run, fake_remotes, monkeypatch):
    first = run()
    change_index(monkeypatch)
    second = run()
    assert fake_remotes.requests != []
    assert second["stats"]["computed"]["index"] != first["stats"]["computed"]["index"]
    assert second["stats"]["audio"]["status"] == "ok"


def test_stats_recomputed_with_force_stats(run, fake_remotes):
    run()
    run("--force-stats")
    assert fake_remotes.requests != []


def test_stats_kept_with_no_stats(run, fake_remotes, monkeypatch):
    first = run()
    change_index(monkeypatch)  # a normal run would recompute now
    second = run("--no-stats")
    assert fake_remotes.requests == []
    assert second["stats"] == first["stats"]


def test_better_stats_kept_when_new_ones_are_worse(run, fake_remotes):
    first = run("--local", "--datasets-dir", LOCAL_DIR)
    assert first["stats"]["computed"]["mode"] == "local"
    fake_remotes.failures["annotations.zip"] = "404"
    second = run("--force-stats")  # remote: annotations needs_local
    assert fake_remotes.requests != []  # it was computed...
    assert second["stats"] == first["stats"]  # ...but the local ok was kept


def test_needs_local_replaced_by_local_run(run, fake_remotes):
    fake_remotes.failures["annotations.zip"] = "404"
    first = run()
    assert first["stats"]["annotations"]["status"] == "needs_local"
    second = run("--local", "--datasets-dir", LOCAL_DIR)
    assert second["stats"]["computed"]["mode"] == "local"
    assert second["stats"]["audio"]["status"] == "ok"
    assert second["stats"]["annotations"]["status"] == "ok"


def test_stats_kept_when_local_copy_is_missing(run, tmp_path):
    first = run()
    second = run("--local", "--datasets-dir", str(tmp_path / "empty"))
    assert second["stats"] == first["stats"]


def test_needs_local_dataset_listed_at_the_end(run, fake_remotes):
    fake_remotes.failures["annotations.zip"] = "404"
    run()
    to_do = run.out[run.out.index("Run these locally") :]
    assert "fake_dataset" in to_do
    assert "annotations" in to_do


def test_fetched_files_deleted_after_the_run(run, tmp_path, monkeypatch):
    temp = tmp_path / "temp"  # the system's temporary folder, for this test
    temp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(temp))
    card = run()
    assert card["stats"]["annotations"]["status"] == "ok"  # the files were fetched and read...
    assert files_under(temp) == []  # ...and nothing is left of them
