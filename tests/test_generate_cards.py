"""scripts/generate_cards.py, run end to end through main() like the workflow runs it.

mirdata knows only fake_dataset here, its remotes are on the fake server, and
llm.summary is a stand-in that records its calls (no model is loaded).
"""

import os
import sys
import tempfile

import mirdata
import pytest

import card_utils
import fake_dataset_loader
import generate_cards
import llm
from fake_dataset_loader import RESOURCES

LOCAL_COPIES = os.path.join(RESOURCES, "mir_datasets")  # holds fake_dataset/
NEW_DOCSTRING = "A new docstring."


@pytest.fixture(autouse=True)
def llm_calls(monkeypatch):
    """llm.summary replaced by a stand-in; the list holds the (name, docstring) of each call."""
    calls = []

    def summary(name, docstring):
        calls.append((name, docstring))
        return f"Summary of {name}."

    monkeypatch.setattr(llm, "summary", summary)
    return calls


@pytest.fixture
def run(fake_remotes, tmp_path, monkeypatch):
    """run(*flags): generate_cards.main() with these flags; returns fake_dataset's card or None."""
    monkeypatch.setattr(mirdata, "DATASETS", ["fake_dataset"])
    (tmp_path / "tmp").mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "tmp"))  # the fetch folder
    cards = tmp_path / "cards"

    def run(*flags):
        argv = ["generate_cards.py", "--output", str(cards), *flags]
        monkeypatch.setattr(sys, "argv", argv)
        generate_cards.main()
        return card_utils.read_card(str(cards / "fake_dataset.yaml"))

    return run


def edit_card(tmp_path, change):
    """Change the written card in place, as if an older run had written it."""
    path = str(tmp_path / "cards" / "fake_dataset.yaml")
    card = card_utils.read_card(path)
    change(card)
    card_utils.write_card(path, card)


def older_index(card):
    card["stats"]["computed"]["index"] = "an older index"


# ----------------------------------------------------------- first run, rerun


def test_generate_cards(run, llm_calls, fake_remotes, tmp_path):
    card = run()
    docstring = llm.loader_docstring("fake_dataset")
    one_call = [("fake_dataset", docstring)]
    assert llm_calls == one_call, "the LLM should run once, on the loader docstring"
    summary = "Summary of fake_dataset."
    assert card["summary"] == summary, "summary should be the LLM's answer"
    hashed = card_utils.docstring_hash(docstring)
    assert card["docstring_hash"] == hashed, "the hash should be the docstring's"

    stats = card["stats"]
    checksum = fake_dataset_loader.INDEXES["1.0"].remote.checksum
    computed = {"mode": "remote", "index": checksum}
    assert stats["computed"] == computed, "stats should record the mode and index"
    assert fake_remotes.requests, "the stats should come from the remotes"
    leftovers = os.listdir(tmp_path / "tmp")
    assert leftovers == [], "the fetched files should be deleted after the run"


def test_generate_cards_rerun(run, llm_calls, fake_remotes):
    first = run()
    llm_calls.clear()
    fake_remotes.requests.clear()
    second = run()
    assert llm_calls == [], "an unchanged docstring should not run the LLM again"
    requests = fake_remotes.requests
    assert requests == [], "stats from the same index should not be computed again"
    assert second == first, "nothing changed, so the card should not change"


# ------------------------------------------------------- what triggers a redo


def test_generate_cards_docstring_changed(run, llm_calls, fake_remotes, monkeypatch):
    first = run()
    llm_calls.clear()
    fake_remotes.requests.clear()
    monkeypatch.setattr(fake_dataset_loader, "__doc__", NEW_DOCSTRING)
    card = run()
    assert len(llm_calls) == 1, "a changed docstring should run the LLM again"
    hashed = card_utils.docstring_hash(NEW_DOCSTRING)
    assert card["docstring_hash"] == hashed, "the hash should be the new docstring's"
    assert fake_remotes.requests == [], "the stats should not be computed again"
    assert card["stats"] == first["stats"], "the stats should be kept"


def test_generate_cards_index_changed(run, llm_calls, fake_remotes, tmp_path):
    first = run()
    edit_card(tmp_path, older_index)
    llm_calls.clear()
    fake_remotes.requests.clear()
    card = run()
    assert fake_remotes.requests, "stats from another index should be computed again"
    assert (
        card["stats"] == first["stats"]
    ), "the recomputed stats should carry the current index"
    assert llm_calls == [], "the summary should not be redone"


def test_generate_cards_force(run, llm_calls, fake_remotes):
    run()
    llm_calls.clear()
    fake_remotes.requests.clear()
    run("--force")
    assert len(llm_calls) == 1, "--force should redo the summary"
    assert fake_remotes.requests == [], "--force should not recompute the stats"

    llm_calls.clear()
    run("--force-stats")
    assert fake_remotes.requests, "--force-stats should recompute current stats"
    assert llm_calls == [], "--force-stats should not redo the summary"


def test_generate_cards_no_docstring(run, llm_calls, monkeypatch):
    monkeypatch.setattr(fake_dataset_loader, "__doc__", None)
    card = run()
    assert llm_calls == [], "a loader without a docstring should not run the LLM"
    assert card["summary"] is None, "without a docstring, summary should be null"
    assert (
        card["docstring_hash"] is None
    ), "without a docstring, docstring_hash should be null"


# --------------------------------------------- flags that switch parts off


def test_generate_cards_no_summary(run, llm_calls, monkeypatch):
    card = run("--no-summary")
    assert llm_calls == [], "--no-summary should never run the LLM"
    assert card["summary"] is None, "a new card should get no summary"

    first = run()
    llm_calls.clear()
    monkeypatch.setattr(fake_dataset_loader, "__doc__", NEW_DOCSTRING)
    card = run("--no-summary")
    assert (
        llm_calls == []
    ), "--no-summary should not run the LLM, even for a new docstring"
    assert card["summary"] == first["summary"], "the old summary should be kept"
    old_hash = first["docstring_hash"]
    assert card["docstring_hash"] == old_hash, "the old summary's hash should be kept"


def test_generate_cards_no_stats(run, fake_remotes, tmp_path):
    card = run("--no-stats")
    assert fake_remotes.requests == [], "--no-stats should send no request"
    assert card["stats"] is None, "a new card should get no stats"

    run()
    edit_card(tmp_path, older_index)
    fake_remotes.requests.clear()
    card = run("--no-stats")
    assert fake_remotes.requests == [], "--no-stats should not recompute old stats"
    index = card["stats"]["computed"]["index"]
    assert index == "an older index", "the old stats should be kept as they are"


def test_generate_cards_local(run, fake_remotes, tmp_path):
    empty = tmp_path / "no_copies"
    empty.mkdir()
    card = run("--local", "--datasets-dir", str(empty))
    assert card["stats"] is None, "a new card without a local copy should get no stats"

    card = run("--local", "--datasets-dir", LOCAL_COPIES)
    stats = card["stats"]
    assert stats["computed"]["mode"] == "local", "--local should read the local copy"
    assert stats["annotations"]["status"] == "ok", (
        "--local should read the dataset's folder inside --datasets-dir,"
        " so nothing is missing"
    )
    assert fake_remotes.requests == [], "--local should send no request"

    again = run("--local", "--datasets-dir", str(empty))
    assert again["stats"] == stats, "without a local copy, the old stats should be kept"


def test_generate_cards_missing(run, llm_calls, monkeypatch):
    card = run("--missing")
    assert card is not None, "--missing should write a dataset that has no card"
    llm_calls.clear()
    monkeypatch.setattr(fake_dataset_loader, "__doc__", NEW_DOCSTRING)
    again = run("--missing")  # a plain run would redo the summary now
    assert llm_calls == [], "--missing should not touch a dataset that has a card"
    assert again == card, "--missing should leave existing cards as they are"


# --------------------------------------------------- keeping the better stats


def test_generate_cards_keeps_more_complete(run, fake_remotes):
    local = run("--local", "--datasets-dir", LOCAL_COPIES)
    fake_remotes.failures["annotations.zip"] = "404"
    card = run("--force-stats")
    assert fake_remotes.requests, "the remote run should have been tried"
    assert card["stats"] == local["stats"], (
        "a remote run that ends needs_local should not replace"
        " local ok stats of the same index"
    )


@pytest.mark.parametrize("problem", ["missing library", "loader error"])
def test_generate_cards_broken_dataset(run, monkeypatch, tmp_path, problem):
    monkeypatch.setattr(mirdata, "DATASETS", ["fake_dataset", "broken_dataset"])
    if problem == "loader error":
        initialize = mirdata.initialize

        def initialize_or_fail(name, *args, **kwargs):
            if name == "broken_dataset":
                raise RuntimeError("loader bug")
            return initialize(name, *args, **kwargs)

        monkeypatch.setattr(mirdata, "initialize", initialize_or_fail)
    # without the patch, broken_dataset has no loader module: ModuleNotFoundError
    card = run()
    assert card is not None, "the other datasets should still get their card"
    broken = tmp_path / "cards" / "broken_dataset.yaml"
    assert not broken.exists(), f"a dataset with a {problem} should be skipped"
