"""Remote mode when something goes wrong: the server, the zips, the limits, broken files.

Each test breaks one thing and checks the status the docs promise
(scripts/scripts_structure.md, "Status of each part"):
    needs_local   the remotes cannot give a complete answer; problems say why
    incomplete    some files are broken in a way a local copy would not fix
A broken remote costs only its own part: the other part stays as in a local run.
"""

import io
import shutil
import socket
import tarfile
import time
import zipfile

import pytest

import fake_dataset
from conftest import dataset_files, zip_bytes
from fake_dataset import DATA_HOME
from stats import dataset
from stats.annotations import remote_files

PARTS = ("audio", "annotations")  # each part has its own zip: audio.zip, annotations.zip
OTHER = {"audio": "annotations", "annotations": "audio"}


@pytest.fixture(autouse=True)
def waits(monkeypatch):
    """Skip the waits between retries (up to 31 s); the list records each wait in seconds."""
    waits = []
    monkeypatch.setattr(time, "sleep", waits.append)
    return waits


def remote_run(tmp_path, **kwargs):
    return dataset.compute("fake_dataset", str(tmp_path / "fetch"), **kwargs)


def local_run(data_home=DATA_HOME):
    return dataset.compute("fake_dataset", data_home, local=True)


def without_sources(part):
    return {k: v for k, v in part.items() if k != "sources"}


def assert_needs_local(part, because):
    """The part asks for a local run, and one of its problems names the reason (a remote, the limit)."""
    assert part["status"] == "needs_local"
    assert any(because in problem for problem in part["problems"]), part["problems"]


def assert_like_local(result, part):
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


@pytest.mark.parametrize("mode", ["404", "403", "short range"])
@pytest.mark.parametrize("part", PARTS)
def test_server_error_needs_local(fake_remotes, tmp_path, part, mode):
    fake_remotes.failures[f"{part}.zip"] = mode
    result = remote_run(tmp_path)
    assert_needs_local(result[part], f"{part}.zip")
    assert_like_local(result, OTHER[part])


@pytest.mark.parametrize("part", PARTS)
def test_server_down_needs_local(fake_remotes, tmp_path, part):
    fake_dataset.REMOTES[part].url = closed_port_url(f"{part}.zip")
    result = remote_run(tmp_path)
    assert_needs_local(result[part], f"{part}.zip")
    assert_like_local(result, OTHER[part])


def test_rate_limit_waits_as_asked_and_retries(fake_remotes, tmp_path, waits):
    fake_remotes.failures.update({"audio.zip": "429 once", "annotations.zip": "429 once"})
    result = remote_run(tmp_path)
    assert len(waits) == 2 and all(w >= 3 for w in waits)  # one wait per 429, Retry-After: 3
    assert_like_local(result, "audio")
    assert_like_local(result, "annotations")


@pytest.mark.parametrize("mode", ["no length", "ignore range"])
def test_annotation_zip_without_range_support_is_downloaded_whole(fake_remotes, tmp_path, mode):
    fake_remotes.failures["annotations.zip"] = mode
    result = remote_run(tmp_path)
    assert_like_local(result, "annotations")
    assert_like_local(result, "audio")


@pytest.mark.parametrize("mode", ["no length", "ignore range"])
def test_audio_zip_without_range_support_needs_local(fake_remotes, tmp_path, mode):
    fake_remotes.failures["audio.zip"] = mode
    result = remote_run(tmp_path)
    assert_needs_local(result["audio"], "audio.zip")
    assert_like_local(result, "annotations")


@pytest.mark.parametrize("mode", ["no length", "ignore range"])
def test_audio_part_never_downloads_the_audio_zip(fake_remotes, tmp_path, mode):
    """Even when the server answers with the whole file, the audio part stops reading at once."""
    files = {**dataset_files("audio"), "audio/padding.bin": bytes(50_000_000)}  # a 50 MB audio zip
    fake_remotes.files["audio.zip"] = zip_bytes(files, zipfile.ZIP_STORED)
    fake_remotes.failures["audio.zip"] = mode
    remote_run(tmp_path, parts=["audio"])
    assert fake_remotes.sent.get("audio.zip", 0) < 10_000_000


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


def test_annotations_part_does_not_download_a_zip_without_annotation_files(fake_remotes, tmp_path):
    """audio.zip holds no annotation file: the annotations part reads its file list (a few KB), not the zip."""
    result = remote_run(tmp_path, parts=["annotations"])
    assert result["annotations"]["status"] == "ok"
    assert bytes_asked(fake_remotes, "audio.zip") < len(fake_remotes.files["audio.zip"]) / 10


# ------------------------------------------------------- 2. the zip or the index


@pytest.mark.parametrize("part", PARTS)
def test_html_page_instead_of_a_zip_needs_local(fake_remotes, tmp_path, part):
    fake_remotes.files[f"{part}.zip"] = b"<html><body>Please log in</body></html>"
    result = remote_run(tmp_path)
    assert_needs_local(result[part], f"{part}.zip")
    assert_like_local(result, OTHER[part])


@pytest.mark.parametrize("part", PARTS)
def test_truncated_zip_needs_local(fake_remotes, tmp_path, part):
    data = fake_remotes.files[f"{part}.zip"]
    fake_remotes.files[f"{part}.zip"] = data[: len(data) // 2]
    result = remote_run(tmp_path)
    assert_needs_local(result[part], f"{part}.zip")
    assert_like_local(result, OTHER[part])


@pytest.mark.parametrize("big", [False, True], ids=["downloaded whole", "read by range"])
def test_corrupt_file_in_the_zip_is_incomplete(fake_remotes, tmp_path, monkeypatch, big):
    """One member's bytes changed after zipping (its CRC no longer matches): only that file is lost."""
    if big:
        monkeypatch.setattr(remote_files, "MAX_ARCHIVE_MB", 0)  # every zip counts as big
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


@pytest.mark.parametrize("part", PARTS)
def test_tar_remote_needs_local(fake_remotes, tmp_path, part):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for path, data in dataset_files(part).items():
            info = tarfile.TarInfo(path)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    fake_remotes.files[f"{part}.tar.gz"] = buffer.getvalue()
    fake_dataset.REMOTES[part].filename = f"{part}.tar.gz"
    fake_dataset.REMOTES[part].url = fake_remotes.url(f"{part}.tar.gz")
    result = remote_run(tmp_path)
    assert_needs_local(result[part], f"{part}.tar.gz")
    assert_like_local(result, OTHER[part])


@pytest.mark.parametrize(
    "part, path, listed_in",
    [
        ("audio", "audio/track3.wav", "errors"),
        ("annotations", "annotations/beats/track3.txt", "missing_files"),
    ],
)
def test_file_missing_from_the_zip_needs_local(fake_remotes, tmp_path, part, path, listed_in):
    files = dataset_files(part)
    del files[path]
    fake_remotes.files[f"{part}.zip"] = zip_bytes(files)
    result = remote_run(tmp_path)
    assert_needs_local(result[part], "not found")
    assert path in result[part][listed_in]
    assert_like_local(result, OTHER[part])


@pytest.mark.parametrize("part", PARTS)
def test_wrapper_folder_in_the_zip_is_stripped(fake_remotes, tmp_path, part):
    """Like GitHub archives: everything inside fake_dataset-main/, which mirdata moves up when unpacking."""
    files = {f"fake_dataset-main/{path}": data for path, data in dataset_files(part).items()}
    fake_remotes.files[f"{part}.zip"] = zip_bytes(files)
    fake_dataset.REMOTES[part].unpack_directories = ["fake_dataset-main"]
    assert_like_local(remote_run(tmp_path), part)


@pytest.mark.parametrize("part", PARTS)
def test_destination_dir_is_added_to_the_member_names(fake_remotes, tmp_path, part):
    """The zip holds track1.wav, mirdata unpacks it into audio/ (the remote's destination_dir)."""
    files = {path.split("/", 1)[1]: data for path, data in dataset_files(part).items()}
    fake_remotes.files[f"{part}.zip"] = zip_bytes(files)
    fake_dataset.REMOTES[part].destination_dir = part
    assert_like_local(remote_run(tmp_path), part)


# ------------------------------------------------------- 3. limits and broken files


def test_mb_limit_stops_the_annotations_but_not_the_audio_headers(fake_remotes, tmp_path):
    result = remote_run(tmp_path, max_mb=0.0001)  # 100 bytes: less than annotations.zip
    assert_needs_local(result["annotations"], "remote limit")
    assert_like_local(result, "audio")  # header reads do not count toward the MB limit


def test_time_limit_stops_both_parts(fake_remotes, tmp_path):
    result = remote_run(tmp_path, max_minutes=0)
    for part in PARTS:
        assert_needs_local(result[part], "remote limit")


def run_with_changed_files(mode, changes, server, tmp_path):
    """compute, local or remote, on the fake dataset with some files replaced ({index path: bytes})."""
    if mode == "local":
        home = tmp_path / "fake_dataset"
        shutil.copytree(DATA_HOME, home)
        for path, data in changes.items():
            (home / path).write_bytes(data)
        return local_run(str(home))
    for part in PARTS:
        files = {**dataset_files(part), **{p: d for p, d in changes.items() if p.startswith(part)}}
        server.files[f"{part}.zip"] = zip_bytes(files)
    return remote_run(tmp_path)


@pytest.mark.parametrize("mode", ["local", "remote"])
def test_corrupt_audio_file_is_incomplete(fake_remotes, tmp_path, mode):
    result = run_with_changed_files(mode, {"audio/track1.wav": b"not a wav file"}, fake_remotes, tmp_path)
    audio = result["audio"]
    assert audio["status"] == "incomplete"
    assert audio["problems"] == []
    assert set(audio["errors"]) == {"audio/track1.wav"}
    assert audio["n_tracks_counted"] == 2
    assert audio["total_seconds"] == 5.0  # track2 (4 s) + track3 (1 s)
    assert audio["sample_rates"] == {8000: 1, 16000: 1}
    assert result["annotations"]["status"] == "ok"


@pytest.mark.parametrize("mode", ["local", "remote"])
def test_corrupt_annotation_file_is_incomplete(fake_remotes, tmp_path, mode):
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
