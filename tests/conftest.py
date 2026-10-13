"""Shared fixtures: the fake dataset of fake_dataset.py, registered in mirdata, and its remotes."""

import io
import os
import sys
import zipfile

import mirdata
import pytest
from mirdata.download_utils import RemoteFileMetadata

import fake_dataset
from fake_server import FakeServer


@pytest.fixture
def fake_mirdata(monkeypatch):
    """mirdata with fake_dataset in its list of datasets, as if it were one of its loaders."""
    monkeypatch.setitem(sys.modules, "mirdata.datasets.fake_dataset", fake_dataset)
    monkeypatch.setattr(mirdata, "DATASETS", [*mirdata.DATASETS, "fake_dataset"])


def dataset_files(folder):
    """{index path: bytes} of the fake dataset's files under folder ("audio" or "annotations")."""
    files = {}
    for root, _, names in os.walk(os.path.join(fake_dataset.DATA_HOME, folder)):
        for name in sorted(names):
            path = os.path.join(root, name)
            with open(path, "rb") as f:
                files[os.path.relpath(path, fake_dataset.DATA_HOME)] = f.read()
    return files


def files_under(folder):
    """Sorted paths, relative to folder, of every file below it."""
    return sorted(
        os.path.relpath(os.path.join(root, name), folder)
        for root, _, names in os.walk(folder)
        for name in names
    )


def zip_bytes(files, compression=zipfile.ZIP_DEFLATED):
    """A zip of {member name: bytes}."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buffer.getvalue()


@pytest.fixture
def server():
    """A FakeServer running for the test."""
    s = FakeServer()
    s.start()
    yield s
    s.stop()


@pytest.fixture
def fake_remotes(fake_mirdata, server, monkeypatch):
    """fake_dataset with two remotes on the local server, audio.zip and annotations.zip.

    The remotes are fake_dataset.REMOTES["audio"] and ["annotations"]; a test
    may change them, or the served files in server.files, before computing.
    """
    server.files["audio.zip"] = zip_bytes(dataset_files("audio"), zipfile.ZIP_STORED)  # audio barely compresses
    server.files["annotations.zip"] = zip_bytes(dataset_files("annotations"))
    remotes = {
        key: RemoteFileMetadata(filename=f"{key}.zip", url=server.url(f"{key}.zip"), checksum="")
        for key in ("audio", "annotations")
    }
    monkeypatch.setattr(fake_dataset, "REMOTES", remotes)
    return server
