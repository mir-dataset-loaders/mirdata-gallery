"""scripts/card_utils.py: storing cards, the two checksums, and picking datasets."""

import hashlib
import os

import mirdata
import pytest
from mirdata import download_utils

from card_utils import (
    card_path,
    docstring_hash,
    index_checksum,
    read_card,
    select_datasets,
    write_card,
)
from fake_dataset_loader import RESOURCES

CARD = {
    "name": "fake_dataset",
    "license": "Creative Commons Attribution 4.0 International",
    "annotations": ["BeatData", "ChordData"],
    "bibtex": "@misc{fake_dataset,\n  title={A fake dataset}\n}",
    "summary": "Beats and chords of three tracks, annotated à la main.",
    "stats": {"tempo": {"unit": "bpm", "edges": [0, 100, 200], "counts": [1, 1]}},
}


def test_write_card(tmp_path):
    path = str(tmp_path / "fake_dataset.yaml")
    write_card(path, CARD)
    card = read_card(path)
    assert card == CARD, "a card should read back exactly as it was written"
    assert list(card) == list(CARD), "fields should stay in the order given, not sorted"

    with open(path, encoding="utf-8") as f:
        text = f.read()
    assert "bibtex: |" in text, "multi-line text should use the | block style"
    assert "edges: [0, 100, 200]" in text, "number lists should sit on one line"
    assert "- BeatData\n" in text, "other lists should have one item per line"
    assert "à la main" in text, "non-ASCII text should be written as it is"


def test_read_card(tmp_path):
    missing = read_card(str(tmp_path / "nowhere.yaml"))
    assert missing is None, "a missing card should read as None"
    path, expected = card_path("cards", "fake_dataset"), "cards/fake_dataset.yaml"
    assert path == expected, "a card should be <cards>/<name>.yaml"


def test_docstring_hash():
    text, changed = "A fake dataset for the tests.", "A fake dataset for the test."
    same = docstring_hash(text) == docstring_hash(text)
    assert same, "the same text should give the same hash"
    different = docstring_hash(changed) != docstring_hash(text)
    assert different, "a one-character change should change the hash"


def test_index_checksum(fake_mirdata, monkeypatch):
    def no_download(*args, **kwargs):
        raise AssertionError("the index should not be downloaded")

    monkeypatch.setattr(download_utils, "download_from_remote", no_download)
    ds = mirdata.initialize("fake_dataset")
    with open(os.path.join(RESOURCES, "fake_dataset_index_1.0.json"), "rb") as f:
        md5 = hashlib.md5(f.read()).hexdigest()
    checksum = index_checksum(ds)
    assert (
        checksum == md5
    ), "index_checksum should be the checksum mirdata publishes: the index file's MD5"


def test_select_datasets():
    names = ["beatles", "guitarset", "orchset"]
    assert select_datasets(names) == names, "no --dataset should select every dataset"
    one = select_datasets(names, "guitarset")
    assert one == ["guitarset"], "--dataset should select just that one"
    with pytest.raises(SystemExit):
        select_datasets(names, "no_such_dataset")
    kept = select_datasets(names, exclude="beatles, orchset")
    assert kept == ["guitarset"], "--exclude should drop a comma-separated list"
