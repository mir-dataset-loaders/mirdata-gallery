"""compute() in remote mode, against the fake remote server (tests/fake_remote_server.py).

The fake dataset's remotes are audio.zip, annotations.zip and metadata.csv on a
local server (conftest.py, fake_remotes). A remote run should give exactly the
numbers of a local run, or say why it cannot (needs_local). Only
test_real_server_supports_range goes online.
"""

import io
import socket
import tarfile
import time
import zipfile

import mirdata
import pytest
import requests

import fake_dataset_loader
from fake_dataset_loader import DATA_HOME
from fake_remote_server import dataset_files, zip_bytes
from stats import annotations, compute, load_index

ANNOTATION_FILES = [
    "annotations/beats/track1.txt",
    "annotations/beats/track2.txt",
    "annotations/beats/track3.txt",
    "annotations/chords/track1.lab",
    "annotations/chords/track2.lab",
]


@pytest.fixture(autouse=True)
def waits(monkeypatch):
    """Retry waits are recorded instead of slept (the list holds each wait in seconds)."""
    waits = []
    monkeypatch.setattr(time, "sleep", waits.append)
    return waits


def remote_run(tmp_path, **kwargs):
    return compute("fake_dataset", str(tmp_path / "fetch"), **kwargs)


def local_run(**kwargs):
    return compute("fake_dataset", DATA_HOME, local=True, **kwargs)


def without_sources(part):
    """A part without its log lines, which say where the files came from."""
    return {key: value for key, value in part.items() if key != "sources"}


def saved_files(folder):
    return sorted(str(p.relative_to(folder)) for p in folder.rglob("*") if p.is_file())


def bytes_asked(server, name):
    """How many bytes of one file the GET requests asked for (a GET without Range: all)."""
    size = len(server.files[name])
    total = 0
    for byte_range in server.gets(name):
        if byte_range is None:
            total += size
        else:
            start, end = map(int, byte_range.removeprefix("bytes=").split("-"))
            total += min(end, size - 1) - start + 1
    return total


def closed_port_url(name):
    """A URL on 127.0.0.1 where no server listens."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    return f"http://127.0.0.1:{port}/{name}"


def serve_annotations(server, files):
    """Serve annotations.zip with these {member name: bytes} instead."""
    server.files["annotations.zip"] = zip_bytes(files)


# ------------------------------------------------------------- nothing broken


def test_remote(fake_remotes, tmp_path):
    remote, local = remote_run(tmp_path), local_run()
    for part in ("audio", "annotations"):
        assert without_sources(remote[part]) == without_sources(
            local[part]
        ), f"remote {part} should equal a local run, apart from the log lines"

    saved = saved_files(tmp_path / "fetch")
    expected = ANNOTATION_FILES + ["metadata.csv"]
    assert (
        saved == expected
    ), "only the annotation files and the metadata file should be saved, no audio"
    audio_zip = len(fake_remotes.files["audio.zip"])
    assert (
        bytes_asked(fake_remotes, "audio.zip") < audio_zip / 10
    ), "a zip with no annotation file should be read only for its table of contents"
    whole = fake_remotes.gets("annotations.zip").count(None)
    assert (
        whole == 1
    ), "a zip under MAX_ARCHIVE_MB should be downloaded whole, in one request"
    metadata_gets = fake_remotes.gets("metadata.csv")
    assert metadata_gets == [None], "a plain file should be downloaded whole"


def test_remote_audio_only(fake_remotes, tmp_path):
    result = remote_run(tmp_path, parts=["audio"])
    assert (
        result["audio"] == local_run()["audio"]
    ), "audio should be counted from the index"
    assert fake_remotes.requests == [], "the audio part should send no request"


def test_remote_big_zip(fake_remotes, tmp_path, monkeypatch):
    monkeypatch.setattr("stats.remote.MAX_ARCHIVE_MB", 0)  # every zip counts as big
    ann = remote_run(tmp_path)["annotations"]
    expected = without_sources(local_run()["annotations"])
    assert (
        without_sources(ann) == expected
    ), "a big zip read by range should give the local numbers"
    gets = fake_remotes.gets("annotations.zip")
    assert None not in gets, "a big zip should never be downloaded whole, only by range"


def test_remote_cached_files(fake_remotes, tmp_path):
    remote_run(tmp_path)
    fake_remotes.requests.clear()
    ann = remote_run(tmp_path)["annotations"]
    assert (
        fake_remotes.requests == []
    ), "files already in the folder should not be fetched again"
    assert ann["status"] == "ok", "a run from cached files should still be ok"


@pytest.mark.parametrize(
    "prefix, unpack_directories, destination_dir",
    [
        # like GitHub archives: everything inside repo-main/, which mirdata moves up
        pytest.param(
            "repo-main/annotations/", ["repo-main"], None, id="wrapper folder"
        ),
        # the zip holds beats/track1.txt, which mirdata unpacks into annotations/
        pytest.param("", None, "annotations", id="destination_dir"),
        # both: repo-main/beats/track1.txt, moved up and unpacked into annotations/
        pytest.param("repo-main/", ["repo-main"], "annotations", id="both"),
    ],
)
def test_remote_zip_layout(
    fake_remotes, tmp_path, prefix, unpack_directories, destination_dir
):
    files = dataset_files("annotations")  # annotations/beats/track1.txt, ...
    inside = {prefix + p.removeprefix("annotations/"): d for p, d in files.items()}
    serve_annotations(fake_remotes, inside)
    remote = fake_dataset_loader.REMOTES["annotations"]
    remote.unpack_directories = unpack_directories
    remote.destination_dir = destination_dir
    ann = remote_run(tmp_path)["annotations"]
    expected = without_sources(local_run()["annotations"])
    assert (
        without_sources(ann) == expected
    ), "zip members should be matched to index paths the way mirdata unpacks the zip"


# ------------------------------------------------- the server or the files break


def break_404(server):
    server.failures["annotations.zip"] = "404"


def break_403(server):
    server.failures["annotations.zip"] = "403"


def break_server_down(server):
    fake_dataset_loader.REMOTES["annotations"].url = closed_port_url("annotations.zip")


def break_web_page(server):
    server.files["annotations.zip"] = b"<html><body>Please log in</body></html>"


def break_truncated(server):
    data = server.files["annotations.zip"]
    server.files["annotations.zip"] = data[: len(data) // 2]


def break_short_range(server):
    server.failures["annotations.zip"] = "short range"


def break_tar(server):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for path, data in dataset_files("annotations").items():
            info = tarfile.TarInfo(path)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    server.files["annotations.tar.gz"] = buffer.getvalue()
    remote = fake_dataset_loader.REMOTES["annotations"]
    remote.filename, remote.url = "annotations.tar.gz", server.url("annotations.tar.gz")


def break_metadata_404(server):
    server.failures["metadata.csv"] = "404"


@pytest.mark.parametrize(
    "break_remote, name",
    [
        (break_404, "annotations.zip"),
        (break_403, "annotations.zip"),
        (break_server_down, "annotations.zip"),
        (break_web_page, "annotations.zip"),
        (break_truncated, "annotations.zip"),
        (break_short_range, "annotations.zip"),
        (break_tar, "annotations.tar.gz"),
        (break_metadata_404, "metadata.csv"),
    ],
    ids=lambda x: getattr(x, "__name__", x).removeprefix("break_"),
)
def test_remote_unreadable_remote(fake_remotes, tmp_path, break_remote, name):
    break_remote(fake_remotes)
    result = remote_run(tmp_path)
    ann = result["annotations"]
    assert (
        ann["status"] == "needs_local"
    ), "a remote that cannot be read should make it needs_local"
    named = any(name in problem for problem in ann["problems"])
    assert named, f"a problem should name the remote that could not be read ({name})"
    assert (
        result["audio"] == local_run()["audio"]
    ), "the audio part should not be affected"


@pytest.mark.parametrize("mode", ["no length", "ignore range"])
def test_remote_no_range_support(fake_remotes, tmp_path, mode):
    fake_remotes.failures["annotations.zip"] = mode
    ann = remote_run(tmp_path)["annotations"]
    expected = without_sources(local_run()["annotations"])
    assert (
        without_sources(ann) == expected
    ), f"a server with {mode} should still work: the zip is downloaded whole"


def test_remote_rate_limit(fake_remotes, tmp_path, waits):
    fake_remotes.failures["annotations.zip"] = "429 once"
    ann = remote_run(tmp_path)["annotations"]
    assert waits and waits[0] >= 3, "a 429 should wait as long as Retry-After asks"
    assert ann["status"] == "ok", "after the wait, the retry should succeed"


@pytest.mark.parametrize(
    "big", [False, True], ids=["downloaded whole", "read by range"]
)
def test_remote_corrupt_file_in_zip(fake_remotes, tmp_path, monkeypatch, big):
    if big:
        monkeypatch.setattr("stats.remote.MAX_ARCHIVE_MB", 0)
    files = dataset_files("annotations")
    good = files["annotations/chords/track1.lab"]
    data = zip_bytes(files, zipfile.ZIP_STORED)  # stored: the file's bytes appear as is
    assert data.count(good) == 1
    corrupt = good.replace(b"C:maj", b"D:maj")  # changed after zipping: wrong CRC
    fake_remotes.files["annotations.zip"] = data.replace(good, corrupt)
    ann = remote_run(tmp_path)["annotations"]
    assert (
        ann["status"] == "incomplete"
    ), "a corrupt file should make it incomplete, not needs_local"
    assert ann["problems"] == [], "a corrupt file is no reason to run locally"
    missing, lost = set(ann["missing_files"]), {"annotations/chords/track1.lab"}
    assert missing == lost, "only the corrupt file should be lost"
    assert (
        ann["annotations"]["chords"]["n_tracks"] == 1
    ), "the property should lose only the track whose file is corrupt"
    assert (
        ann["annotations"]["beats"]["n_tracks"] == 3
    ), "other properties should not be affected"


def test_remote_missing_file(fake_remotes, tmp_path):
    files = dataset_files("annotations")
    del files["annotations/beats/track3.txt"]
    serve_annotations(fake_remotes, files)
    ann = remote_run(tmp_path)["annotations"]
    assert (
        ann["status"] == "needs_local"
    ), "a file no remote holds should make it needs_local"
    assert any(
        "not found" in problem for problem in ann["problems"]
    ), "the problem should say files were not found"
    assert (
        "annotations/beats/track3.txt" in ann["missing_files"]
    ), "missing_files should name the file"


def test_remote_no_remotes(fake_mirdata, tmp_path):
    ann = remote_run(tmp_path)["annotations"]  # fake_dataset_loader.REMOTES is None
    assert (
        ann["status"] == "needs_local"
    ), "a dataset without remotes should be needs_local"
    assert any(
        "no remotes" in problem for problem in ann["problems"]
    ), "the problem should say there are no remotes"


@pytest.mark.parametrize(
    "limit", [{"max_mb": 0.0001}, {"max_minutes": 0}], ids=["size", "time"]
)
def test_remote_budget(fake_remotes, tmp_path, limit):
    ds = mirdata.initialize("fake_dataset", data_home=str(tmp_path))
    ann = annotations.dataset_stats(ds, str(tmp_path), load_index(ds), **limit)
    assert (
        ann["status"] == "needs_local"
    ), "passing the remote budget should make it needs_local"
    hit = any("remote limit" in problem for problem in ann["problems"])
    assert hit, "the problem should say the remote limit was hit"


# ------------------------------------------------------------------ online


@pytest.mark.online
def test_real_server_supports_range():
    """The fake server answers like Zenodo is assumed to: checked here on a real remote, 1 byte read."""
    url = mirdata.initialize("orchset").remotes["all"].url
    head = requests.head(url, allow_redirects=True, timeout=30)
    assert head.status_code == 200, f"{url} should be reachable"
    size = head.headers.get("Content-Length")
    assert size and int(size) > 0, "a real server should report the file size"
    r = requests.get(head.url, headers={"Range": "bytes=0-0"}, timeout=30)
    assert r.status_code == 206, "a range request should get 206, not the whole file"
    assert (
        r.headers.get("Content-Range") == f"bytes 0-0/{size}"
    ), "Content-Range should say which bytes"
    assert (
        r.content == b"P"
    ), "exactly the first byte should come back (a zip starts with PK)"
