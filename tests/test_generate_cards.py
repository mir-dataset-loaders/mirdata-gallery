"""generate_cards.py on the fake dataset: the card it writes, and when its stats and summary are recomputed or kept.

The rules (scripts/scripts_structure.md, "Stats in the cards"):
  - stats are computed when the card has none, the index changed, or with
    --force-stats or --local; otherwise the card keeps its stats;
  - for the same index, the more complete stats win (ok, incomplete,
    needs_local, error, judged by the worst part).
  - the summary is redone only when the loader docstring hashes differently
    from the card's docstring_hash (or the card has no summary, or --force).
Each test runs the command line as a user would, with --no-summary (no LLM),
except the summary tests, which replace llm.summary with a stand-in.
"""

import hashlib
import sys
import tempfile

import pytest

import card_utils
import fake_dataset
import generate_cards
import llm
from conftest import files_under
from fake_dataset import RESOURCES
from test_cards_schema import validate_card

LOCAL_DIR = f"{RESOURCES}/mir_datasets"  # holds fake_dataset/


@pytest.fixture
def run(fake_remotes, tmp_path, monkeypatch, capsys):
    """run(*flags): generate_cards.py for fake_dataset into tmp_path/cards; returns the card.

    The test fails unless the run reports the card as written ([OK]): a run that
    fails leaves the previous card on disk, which would pass for "stats kept".
    run.out holds what the run printed. summary=True leaves out --no-summary
    (use it with llm_calls, or the real model is loaded).
    """
    cards = str(tmp_path / "cards")

    def run(*flags, summary=False):
        argv = ["generate_cards.py", "--dataset", "fake_dataset", "--output", cards]
        if not summary:
            argv.append("--no-summary")
        monkeypatch.setattr(sys, "argv", [*argv, *flags])
        fake_remotes.requests.clear()
        generate_cards.main()
        run.out = capsys.readouterr().out
        assert "[OK]    fake_dataset" in run.out, run.out
        return card_utils.read_card(card_utils.card_path(cards, "fake_dataset"))

    return run


@pytest.fixture
def llm_calls(monkeypatch):
    """llm.summary replaced with a stand-in; the list holds the (name, docstring) of each call."""
    calls = []

    def summary(name, docstring):
        calls.append((name, docstring))
        return f"Summary {len(calls)} of {name}."

    monkeypatch.setattr(llm, "summary", summary)
    return calls


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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


def test_new_card_gets_summary_and_docstring_hash(run, llm_calls):
    card = run(summary=True)
    assert len(llm_calls) == 1
    name, docstring = llm_calls[0]
    assert name == "fake_dataset"
    assert docstring.startswith("A tiny mirdata loader for the tests")
    assert card["summary"] == "Summary 1 of fake_dataset."
    assert card["docstring_hash"] == sha256(docstring)  # the text the summary was made from
    assert validate_card(card, "fake_dataset.yaml") == []


def test_summary_kept_when_docstring_is_unchanged(run, llm_calls):
    first = run(summary=True)
    second = run(summary=True)
    assert len(llm_calls) == 1  # no second LLM call
    assert second["summary"] == first["summary"]
    assert second["docstring_hash"] == first["docstring_hash"]


def test_summary_redone_when_docstring_changes(run, llm_calls, monkeypatch):
    run(summary=True)
    monkeypatch.setattr(fake_dataset, "__doc__", "A new description of the fake dataset.")
    second = run(summary=True)
    assert llm_calls[1:] == [("fake_dataset", "A new description of the fake dataset.")]
    assert second["summary"] == "Summary 2 of fake_dataset."
    assert second["docstring_hash"] == sha256("A new description of the fake dataset.")
