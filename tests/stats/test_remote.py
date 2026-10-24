"""stats/remote.py through compute(): what goes wrong (the server, the zips, the limits,
broken files), and how the zips are read when nothing does (section 4).

Each test in sections 1 to 3 breaks one thing and checks the status the docs promise
(scripts/scripts_structure.md, "Status of each part"):
    needs_local   the remotes cannot give a complete answer; problems say why
    incomplete    some files are broken in a way a local copy would not fix
Only the annotations part reads the remotes: the audio part, counted from the
index, stays as in a local run whatever breaks.
"""

import io
import shutil
import socket
import tarfile
import time
import zipfile

import pytest

import fake_dataset
from conftest import dataset_files, files_under, zip_bytes
from fake_dataset import DATA_HOME
from stats import compute

ZIPS = ("audio", "annotations")  # the server's two zips: audio.zip, annotations.zip


@pytest.fixture(autouse=True)
def waits(monkeypatch):
    """Skip the waits between retries (up to 31 s); the list records each wait in seconds."""
    waits = []
    monkeypatch.setattr(time, "sleep", waits.append)
    return waits


def remote_run(tmp_path, **kwargs):
    return compute("fake_dataset", str(tmp_path / "fetch"), **kwargs)


def local_run(data_home=DATA_HOME):
    return compute("fake_dataset", data_home, local=True)


def without_sources(part):
    return {k: v for k, v in part.items() if k != "sources"}


def assert_needs_local_because(part, reason):
    """The part is needs_local, and one of its problems names the reason (a remote, the limit)."""
    assert part["status"] == "needs_local"
    assert any(reason in problem for problem in part["problems"]), part["problems"]


def assert_same_as_local(result, part):
    """The part was not affected: ok, with exactly the numbers of a local run."""
    assert result[part]["status"] == "ok"
    assert without_sources(result[part]) == without_sources(local_run()[part])


def closed_port_url(name):
    """A URL on 127.0.0.1 where no server listens."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    return f"http://127.0.0.1:{port}/{name}"


# ------------------------------------------------------- 1. the server misbehaves


@pytest.mark.parametrize("status", ["404", "403"])
def test_needs_local_when_server_answers_404_or_403(fake_remotes, tmp_path, status):
    fake_remotes.failures["annotations.zip"] = status
    result = remote_run(tmp_path)
    assert_needs_local_because(result["annotations"], "annotations.zip")
    assert_same_as_local(result, "audio")


def test_needs_local_when_server_sends_fewer_bytes_than_asked(fake_remotes, tmp_path):
    fake_remotes.failures["annotations.zip"] = "short range"
    result = remote_run(tmp_path)
    assert_needs_local_because(result["annotations"], "annotations.zip")
    assert_same_as_local(result, "audio")


def test_needs_local_when_server_is_down(fake_remotes, tmp_path):
    fake_dataset.REMOTES["annotations"].url = closed_port_url("annotations.zip")
    result = remote_run(tmp_path)
    assert_needs_local_because(result["annotations"], "annotations.zip")
    assert_same_as_local(result, "audio")


def test_waits_as_asked_when_rate_limited(fake_remotes, tmp_path, waits):
    fake_remotes.failures.update({"audio.zip": "429 once", "annotations.zip": "429 once"})
    result = remote_run(tmp_path)
    assert len(waits) == 2 and all(w >= 3 for w in waits)  # one wait per 429, Retry-After: 3
    assert_same_as_local(result, "audio")
    assert_same_as_local(result, "annotations")


@pytest.mark.parametrize("mode", ["no length", "ignore range"])
def test_annotations_ok_when_server_has_no_range_support(fake_remotes, tmp_path, mode):
    fake_remotes.failures["annotations.zip"] = mode
    result = remote_run(tmp_path)
    assert_same_as_local(result, "annotations")
    assert_same_as_local(result, "audio")


def bytes_asked(server, name):
    """How many bytes of one file the GET requests asked for (a GET without Range: all of it)."""
    size = len(server.files[name])
    total = 0
    for byte_range in server.gets(name):
        if byte_range is None:
            total += size
        else:
            start, end = map(int, byte_range.removeprefix("bytes=").split("-"))
            total += min(end, size - 1) - start + 1
    return total


def test_zip_not_downloaded_when_it_has_no_annotations(fake_remotes, tmp_path):
    """audio.zip holds no annotation file: the annotations part reads its file list (a few KB), not the zip."""
    result = remote_run(tmp_path, parts=["annotations"])
    assert result["annotations"]["status"] == "ok"
    assert bytes_asked(fake_remotes, "audio.zip") < len(fake_remotes.files["audio.zip"]) / 10


# ------------------------------------------------------- 2. the zip or the index


def test_needs_local_when_server_sends_a_web_page(fake_remotes, tmp_path):
    fake_remotes.files["annotations.zip"] = b"<html><body>Please log in</body></html>"
    result = remote_run(tmp_path)
    assert_needs_local_because(result["annotations"], "annotations.zip")
    assert_same_as_local(result, "audio")


def test_needs_local_when_zip_is_truncated(fake_remotes, tmp_path):
    data = fake_remotes.files["annotations.zip"]
    fake_remotes.files["annotations.zip"] = data[: len(data) // 2]
    result = remote_run(tmp_path)
    assert_needs_local_because(result["annotations"], "annotations.zip")
    assert_same_as_local(result, "audio")


@pytest.mark.parametrize("big", [False, True], ids=["downloaded whole", "read by range"])
def test_incomplete_when_a_file_in_the_zip_is_corrupt(fake_remotes, tmp_path, monkeypatch, big):
    """One member's bytes changed after zipping (its CRC no longer matches): only that file is lost."""
    if big:
        monkeypatch.setattr("stats.remote.MAX_ARCHIVE_MB", 0)  # every zip counts as big
    files = dataset_files("annotations")
    good = files["annotations/chords/track1.lab"]
    data = zip_bytes(files, zipfile.ZIP_STORED)  # stored: the file's bytes appear as is
    assert data.count(good) == 1
    fake_remotes.files["annotations.zip"] = data.replace(good, good.replace(b"C:maj", b"D:maj"))
    ann = remote_run(tmp_path)["annotations"]
    assert ann["status"] == "incomplete"
    assert ann["problems"] == []
    assert set(ann["missing_files"]) == {"annotations/chords/track1.lab"}
    assert ann["annotations"]["beats"]["n_tracks"] == 3
    assert ann["annotations"]["chords"]["n_tracks"] == 1  # track2 only: no D:maj ever read
    assert "D:maj" not in ann["annotations"]["chords"]["labels"]


def test_needs_local_when_remote_is_a_tar(fake_remotes, tmp_path):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for path, data in dataset_files("annotations").items():
            info = tarfile.TarInfo(path)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    fake_remotes.files["annotations.tar.gz"] = buffer.getvalue()
    fake_dataset.REMOTES["annotations"].filename = "annotations.tar.gz"
    fake_dataset.REMOTES["annotations"].url = fake_remotes.url("annotations.tar.gz")
    result = remote_run(tmp_path)
    assert_needs_local_because(result["annotations"], "annotations.tar.gz")
    assert_same_as_local(result, "audio")


def test_needs_local_when_a_file_is_missing_from_the_zip(fake_remotes, tmp_path):
    files = dataset_files("annotations")
    del files["annotations/beats/track3.txt"]
    fake_remotes.files["annotations.zip"] = zip_bytes(files)
    result = remote_run(tmp_path)
    assert_needs_local_because(result["annotations"], "not found")
    assert "annotations/beats/track3.txt" in result["annotations"]["missing_files"]
    assert_same_as_local(result, "audio")


def test_ok_when_zip_has_a_wrapper_folder(fake_remotes, tmp_path):
    """Like GitHub archives: everything inside fake_dataset-main/, which mirdata moves up when unpacking."""
    files = {f"fake_dataset-main/{path}": data for path, data in dataset_files("annotations").items()}
    fake_remotes.files["annotations.zip"] = zip_bytes(files)
    fake_dataset.REMOTES["annotations"].unpack_directories = ["fake_dataset-main"]
    assert_same_as_local(remote_run(tmp_path), "annotations")


def test_ok_when_remote_has_a_destination_dir(fake_remotes, tmp_path):
    """The zip holds beats/track1.txt, mirdata unpacks it into annotations/ (the remote's destination_dir)."""
    files = {path.split("/", 1)[1]: data for path, data in dataset_files("annotations").items()}
    fake_remotes.files["annotations.zip"] = zip_bytes(files)
    fake_dataset.REMOTES["annotations"].destination_dir = "annotations"
    assert_same_as_local(remote_run(tmp_path), "annotations")


# ------------------------------------------------------- 3. limits and broken files


def test_needs_local_for_annotations_only_when_mb_limit_is_hit(fake_remotes, tmp_path):
    result = remote_run(tmp_path, max_mb=0.0001)  # 100 bytes: less than annotations.zip
    assert_needs_local_because(result["annotations"], "remote limit")
    assert_same_as_local(result, "audio")  # the audio part reads no remote


def test_needs_local_for_annotations_only_when_time_limit_is_hit(fake_remotes, tmp_path):
    result = remote_run(tmp_path, max_minutes=0)
    assert_needs_local_because(result["annotations"], "remote limit")
    assert_same_as_local(result, "audio")


def run_with_changed_files(mode, changes, server, tmp_path):
    """compute, local or remote, on the fake dataset with some files replaced ({index path: bytes})."""
    if mode == "local":
        home = tmp_path / "fake_dataset"
        shutil.copytree(DATA_HOME, home)
        for path, data in changes.items():
            (home / path).write_bytes(data)
        return local_run(str(home))
    for part in ZIPS:
        files = {**dataset_files(part), **{p: d for p, d in changes.items() if p.startswith(part)}}
        server.files[f"{part}.zip"] = zip_bytes(files)
    return remote_run(tmp_path)


@pytest.mark.parametrize("mode", ["local", "remote"])
def test_incomplete_when_an_annotation_file_is_corrupt(fake_remotes, tmp_path, mode):
    changes = {"annotations/beats/track2.txt": b"not\ta beat\n"}
    result = run_with_changed_files(mode, changes, fake_remotes, tmp_path)
    ann = result["annotations"]
    assert ann["status"] == "incomplete"
    assert ann["problems"] == []
    assert set(ann["annotation_errors"]) == {"beats"}
    assert set(ann["annotation_errors"]["beats"]["examples"]) == {"track2"}
    assert ann["annotations"]["beats"]["n_tracks"] == 2
    assert ann["annotations"]["chords"]["n_tracks"] == 2  # the chords are not affected
    assert result["audio"]["status"] == "ok"


# ------------------------------------------------------- 4. reading the zips (nothing broken)


def test_small_zip_is_downloaded_whole(fake_remotes, tmp_path):
    """A zip up to 200 MB comes in one piece: fewer requests than the 5 files it holds."""
    compute("fake_dataset", str(tmp_path), parts=["annotations"])
    assert len(fake_remotes.gets("annotations.zip")) < 5


def test_big_zip_is_read_by_range(fake_remotes, tmp_path, monkeypatch):
    monkeypatch.setattr("stats.remote.MAX_ARCHIVE_MB", 0)  # every zip counts as big
    remote = compute("fake_dataset", str(tmp_path), parts=["annotations"])
    local = compute("fake_dataset", DATA_HOME, local=True, parts=["annotations"])
    assert remote["annotations"]["status"] == "ok"
    assert without_sources(remote["annotations"]) == without_sources(local["annotations"])
    assert len(fake_remotes.gets("annotations.zip")) > 1
    assert all(fake_remotes.gets("annotations.zip"))  # every request is a range


def test_only_annotation_files_are_saved(fake_remotes, tmp_path):
    """The fetch folder gets the 5 annotation files and no audio (the audio part reads only the index).

    compute() leaves them there; generate_cards.py deletes the folder after the run (test_generate_cards.py).
    """
    compute("fake_dataset", str(tmp_path))
    assert files_under(tmp_path) == [
        "annotations/beats/track1.txt",
        "annotations/beats/track2.txt",
        "annotations/beats/track3.txt",
        "annotations/chords/track1.lab",
        "annotations/chords/track2.lab",
    ]
