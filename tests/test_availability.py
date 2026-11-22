"""scripts/availability.py: the availability card field, with a stand-in model (no LLM is loaded)."""

import re

import mirdata
import pytest

import llm
from availability import (
    availability,
    availability_hash,
    loader_texts,
    note_label,
    parse_answer,
)
import fake_dataset_loader
from fake_dataset_loader import DATA_HOME

TEXTS = {
    "links": "audio: audio.zip",
    "note": "Request access.",
    "description": "A dataset.",
}


class FakeModel:
    """Stands in for the LLM: replies with `reply` and records each question."""

    def __init__(self, reply):
        self.reply = reply
        self.questions = []

    def create_chat_completion(self, messages, **kwargs):
        self.questions.append(messages[-1]["content"])
        return {"choices": [{"message": {"content": self.reply}}]}


@pytest.fixture
def model(monkeypatch):
    """model(reply): makes llm.get_model() return a FakeModel with this reply."""

    def use(reply):
        fake = FakeModel(reply)
        monkeypatch.setattr(llm, "get_model", lambda: fake)
        return fake

    return use


# ------------------------------------------------------------------ loader_texts


def test_loader_texts(fake_remotes):
    ds = mirdata.initialize("fake_dataset", data_home=DATA_HOME)
    ds._download_info = "\n    Request access here.  \n"
    texts = loader_texts(ds)
    links = "audio: audio.zip\nannotations: annotations.zip\nmetadata: metadata.csv"
    assert (
        texts["links"] == links
    ), "links should be one 'key: filename' line per remote"
    assert texts["note"] == "Request access here.", "the note should be tidied"
    docstring = llm.loader_docstring("fake_dataset")
    assert (
        texts["description"] == docstring
    ), "description should be the loader docstring"


def test_loader_texts_missing(fake_mirdata, monkeypatch):
    monkeypatch.setattr(fake_dataset_loader, "__doc__", None)
    ds = mirdata.initialize("fake_dataset", data_home=DATA_HOME)  # no remotes, no note
    empty = {"links": "", "note": "", "description": ""}
    assert loader_texts(ds) == empty, "missing texts should be empty"


# ------------------------------------------------------------- availability_hash


def test_availability_hash():
    hashed = availability_hash(TEXTS)
    assert re.fullmatch(r"[0-9a-f]{64}", hashed), "the hash should be a SHA-256"
    assert (
        availability_hash(dict(TEXTS)) == hashed
    ), "the same texts should give the same hash"


@pytest.mark.parametrize("key", ["links", "note", "description"])
def test_availability_hash_changes(key):
    changed = {**TEXTS, key: TEXTS[key] + " Changed."}
    assert availability_hash(changed) != availability_hash(
        TEXTS
    ), f"a changed {key} should change the hash"


# ------------------------------------------------------------------ parse_answer


def test_parse_answer():
    answer = "reason: The zip holds both.\n**Audio**: Yes.\nannotations: no"
    found = parse_answer(answer, ("yes", "no", "none"))
    expected = {"audio": "yes", "annotations": "no"}
    assert found == expected, "each part should be read, whatever its case or markdown"


def test_parse_answer_unknown():
    found = parse_answer("audio: maybe", ("yes", "no", "none"))
    expected = {"audio": "unknown", "annotations": "unknown"}
    assert (
        found == expected
    ), "a value not allowed, or a missing part, should be unknown"


# -------------------------------------------------------------------- note_label


@pytest.mark.parametrize(
    "note, label",
    [
        ("Go to Zenodo and request access.", "on request"),
        ("The audio files are not available for download.", "not available"),
        ("The audio must be purchased from the label.", "not available"),
        ("Buy the CDs and rip them.", "not available"),
        ("Not available for free download, but upon request.", "on request"),
        ("Unzip the files into data_home.", "unknown"),
        ("", "unknown"),
    ],
)
def test_note_label(note, label):
    assert note_label(note) == label, f"{note!r} should be {label}"


# ------------------------------------------------------------------ availability


def test_availability_without_links(model):
    fake = model("audio: yes\nannotations: yes")
    found = availability("fake_dataset", {**TEXTS, "links": ""})
    assert fake.questions == [], "without download links the LLM should not be asked"
    expected = {"audio": "on request", "annotations": "on request"}
    assert found == expected, "every part should get the note's label"


@pytest.mark.parametrize(
    "reply, expected",
    [
        ("audio: yes\nannotations: yes", {"audio": "public", "annotations": "public"}),
        (
            "audio: none\nannotations: yes",
            {"audio": "not available", "annotations": "public"},
        ),
        (
            "audio: no\nannotations: yes",
            {"audio": "on request", "annotations": "public"},
        ),
        ("I cannot tell.", {"audio": "on request", "annotations": "on request"}),
    ],
)
def test_availability_with_links(model, reply, expected):
    fake = model(reply)
    found = availability("fake_dataset", TEXTS)
    assert len(fake.questions) == 1, "with download links the LLM should be asked once"
    assert "audio: audio.zip" in fake.questions[0], "the question should hold the links"
    assert found == expected, f"{reply!r} should give {expected}"
