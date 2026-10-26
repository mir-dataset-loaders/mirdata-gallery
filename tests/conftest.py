"""Shared fixtures: the fake dataset registered in mirdata, and its remotes on a local server.

Tests marked `online` use the internet; `pytest --local` skips them.
"""

import os
import sys
import zipfile

import mirdata
import pytest
from mirdata.download_utils import RemoteFileMetadata

import fake_dataset_loader
from fake_dataset_loader import DATA_HOME
from fake_remote_server import FakeRemoteServer, dataset_files, zip_bytes


def pytest_addoption(parser):
    parser.addoption(
        "--local", action="store_true", help="run offline: skip the tests marked online"
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "online: needs the internet (skipped with --local)"
    )


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--local"):
        return
    offline = pytest.mark.skip(reason="--local: offline run")
    for item in items:
        if "online" in item.keywords:
            item.add_marker(offline)


@pytest.fixture
def fake_mirdata(monkeypatch):
    """mirdata with fake_dataset in its list of datasets, as if it were one of its loaders."""
    monkeypatch.setitem(
        sys.modules, "mirdata.datasets.fake_dataset", fake_dataset_loader
    )
    monkeypatch.setattr(mirdata, "DATASETS", [*mirdata.DATASETS, "fake_dataset"])


@pytest.fixture
def fake_remotes(fake_mirdata, monkeypatch):
    """fake_dataset's remotes on a local server: audio.zip, annotations.zip and metadata.csv.

    Returns the running FakeRemoteServer; a test may change its files or
    failures before computing.
    """
    server = FakeRemoteServer()
    with open(os.path.join(DATA_HOME, "metadata.csv"), "rb") as f:
        metadata = f.read()
    # audio barely compresses: stored, not deflated
    audio_zip = zip_bytes(dataset_files("audio"), zipfile.ZIP_STORED)
    server.files = {
        "audio.zip": audio_zip,
        "annotations.zip": zip_bytes(dataset_files("annotations")),
        "metadata.csv": metadata,
    }
    remotes = {
        key: RemoteFileMetadata(filename=name, url=server.url(name), checksum="")
        for key, name in [
            ("audio", "audio.zip"),
            ("annotations", "annotations.zip"),
            ("metadata", "metadata.csv"),
        ]
    }
    monkeypatch.setattr(fake_dataset_loader, "REMOTES", remotes)
    server.start()
    yield server
    server.stop()
