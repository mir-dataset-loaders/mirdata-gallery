"""remote.py against the fake remote server (tests/fake_remote_server.py).

The fake dataset's remotes are audio.zip, annotations.zip and metadata.csv on a
local server (conftest.py, fake_remotes); a test may serve other files. The
server's request log shows what was actually downloaded.
"""

import hashlib
import io
import os
import pathlib
import socket
import tarfile
import time
import unicodedata
import zipfile

import pytest
import requests
from mirdata.download_utils import RemoteFileMetadata

import fake_dataset_loader
from fake_dataset_loader import DATA_HOME
from fake_remote_server import dataset_files, zip_bytes
from stats import remote

ANNOTATION_FILES = {
    "annotations/beats/track1.txt",
    "annotations/beats/track2.txt",
    "annotations/beats/track3.txt",
    "annotations/chords/track1.lab",
    "annotations/chords/track2.lab",
}
WANTED = ANNOTATION_FILES | {"metadata.csv"}  # the fake index's non-audio paths
AUDIO = {"audio/track1.wav", "audio/track2.wav", "audio/track3.wav"}


@pytest.fixture(autouse=True)
def waits(monkeypatch):
    """Retry waits are recorded instead of slept (the list holds each wait in seconds)."""
    waits = []
    monkeypatch.setattr(time, "sleep", waits.append)
    return waits


def fetch_fake(data_home, budget=None):
    """fetch() on the fake dataset's remotes, as annotations.dataset_stats calls it."""
    return remote.fetch(
        fake_dataset_loader.REMOTES, WANTED, AUDIO, str(data_home), budget=budget
    )


def serve(server, name, data, failure=None):
    """Serve data as name (failing in that mode, if given); return its remote."""
    server.files[name] = data
    if failure:
        server.failures[name] = failure
    return RemoteFileMetadata(filename=name, url=server.url(name), checksum="")


def saved_files(folder):
    return sorted(str(p.relative_to(folder)) for p in folder.rglob("*") if p.is_file())


def file_contents(folder, paths):
    """{path: bytes} of these paths under folder."""
    return {path: (pathlib.Path(folder) / path).read_bytes() for path in sorted(paths)}


def ranges(server, name):
    """(first, last) byte of each GET for one file; a GET without Range is the whole file."""
    size = len(server.files[name])
    result = []
    for byte_range in server.gets(name):
        if byte_range is None:
            result.append((0, size - 1))
        else:
            first, last = map(int, byte_range.removeprefix("bytes=").split("-"))
            result.append((first, min(last, size - 1)))
    return result


def track_by_track():
    """The fake dataset's audio and annotation files in one dict, each track's audio first."""
    files = {**dataset_files("audio"), **dataset_files("annotations")}

    def order(path):
        track = os.path.splitext(os.path.basename(path))[0]
        return track, not path.startswith("audio/"), path

    return {path: files[path] for path in sorted(files, key=order)}


def tar_bytes(files):
    """A .tar.gz holding {member name: bytes}."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def closed_port_url(name):
    """A URL on 127.0.0.1 where no server listens."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    return f"http://127.0.0.1:{port}/{name}"


# --------------------------------------------------------------------- Budget


def test_budget_check_refuses_over_limit():
    budget = remote.Budget(max_mb=1)
    budget.add(600_000)
    budget.check(400_000)  # up to the limit is allowed
    with pytest.raises(remote.BudgetExceeded):
        budget.check(400_001)
    assert budget.bytes == 600_000, "a check should never change the bytes counted"


# ------------------------------------------------------------------- HTTPFile


def test_read_at_returns_exact_bytes(fake_remotes):
    data = fake_remotes.files["audio.zip"]
    http = remote.HTTPFile(fake_remotes.url("audio.zip"), requests.Session())
    assert (
        http.read_at(100, 50) == data[100:150]
    ), "read_at should return exactly the bytes asked for"
    assert fake_remotes.gets("audio.zip") == [
        "bytes=100-149"
    ], "read_at should send one request whose Range header names those bytes"


def test_read_at_ignored_range_sets_flag_and_raises(fake_remotes):
    fake_remotes.failures["audio.zip"] = "ignore range"
    budget = remote.Budget(max_mb=100)
    http = remote.HTTPFile(fake_remotes.url("audio.zip"), requests.Session(), budget)
    with pytest.raises(IOError):
        http.read_at(100, 50)
    assert (
        http.ranges_ignored
    ), "a whole-file answer to a range request should set ranges_ignored"
    assert (
        http.bytes == 0 and budget.bytes == 0
    ), "the whole file sent instead should not be read"


def test_read_at_refused_by_budget_before_request(fake_remotes):
    budget = remote.Budget(max_mb=50 / 1e6)  # 50 bytes
    http = remote.HTTPFile(fake_remotes.url("audio.zip"), requests.Session(), budget)
    with pytest.raises(remote.BudgetExceeded):
        http.read_at(0, 100)
    assert (
        fake_remotes.gets("audio.zip") == []
    ), "a read that would pass the budget should send no request"


# ----------------------------------------------------------- download_to_file


def test_download_refused_by_content_length(fake_remotes):
    budget = remote.Budget(max_mb=100 / 1e6)  # 100 bytes
    file = io.BytesIO()
    with pytest.raises(remote.BudgetExceeded):
        remote.download_to_file(
            fake_remotes.url("audio.zip"), file, requests.Session(), budget
        )
    assert (
        budget.bytes == 0
    ), "a Content-Length over the budget should be refused unread"
    assert file.getvalue() == b"", "a refused download should write nothing"


# ---------------------------------------------------------------- index_paths


def test_index_paths_splits_audio_and_non_audio():
    index = {
        "tracks": {
            "track1": {
                "audio_mono": ["audio/track1_mono.wav", "md5"],
                "beats": ["annotations/track1.beats", "md5"],
                "chords": [None, None],
            },
        },
        "multitracks": {
            "song1": {
                "tracks": ["track1"],
                "audio_mix": ["audio/song1_mix.wav", "md5"],
                "notes": ["annotations/song1.mid", "md5"],
            },
        },
        "metadata": {"titles": ["metadata/titles.csv", "md5"]},
    }
    non_audio, audio = remote.index_paths(index)
    expected_non_audio = {
        "annotations/track1.beats",
        "annotations/song1.mid",
        "metadata/titles.csv",
    }
    expected_audio = {"audio/track1_mono.wav", "audio/song1_mix.wav"}
    assert (
        non_audio == expected_non_audio
    ), "every file whose key has no 'audio', and every metadata file, should be non-audio"
    assert (
        audio == expected_audio
    ), "every track or multitrack file whose key contains 'audio' should be audio"


# ----------------------------------------------------------------- match_name


def test_match_name_unicode_nfd_vs_nfc():
    path = unicodedata.normalize("NFC", "annotations/André.txt")  # é: one character
    name = unicodedata.normalize("NFD", path)  # é: e + accent, as macOS writes it
    assert (
        remote.match_name(name, {path: path}) == path
    ), "an archive name in NFD should match the same index path in NFC"


# ---------------------------------------------------------------- fetch_plain


def test_fetch_plain_removes_partial_file_on_failure(fake_remotes, tmp_path):
    # Without a size, the budget can only stop the download midway; it arrives
    # in 1 MB pieces, so the first one is written before the budget stops it.
    plain = serve(fake_remotes, "big.csv", b"x" * 3_000_000, failure="no length")
    budget = remote.Budget(max_mb=1.5)
    with pytest.raises(remote.BudgetExceeded):
        remote.fetch_plain(plain, str(tmp_path), requests.Session(), budget)
    assert budget.bytes > 0, "the download should start before the budget stops it"
    assert (
        saved_files(tmp_path) == []
    ), "a download stopped midway should leave no partial file"


# ------------------------------------------------------------------------ Zip


def test_open_zip_with_range_reads_only_file_list(fake_remotes):
    data = fake_remotes.files["audio.zip"]
    file_list_start = zipfile.ZipFile(io.BytesIO(data)).start_dir
    zf, http = remote.open_zip(fake_remotes.url("audio.zip"), requests.Session())
    assert (
        http is not None
    ), "a server with range support should not need a whole download"
    assert set(zf.namelist()) == set(
        dataset_files("audio")
    ), "the zip's file list should be read"
    asked = ranges(fake_remotes, "audio.zip")
    assert all(
        first >= file_list_start for first, _ in asked
    ), "only the file list at the end of the zip should be downloaded"


def test_fetch_zip_with_audio_never_requests_audio(fake_remotes, tmp_path):
    data = zip_bytes(track_by_track(), zipfile.ZIP_STORED)
    bundle = serve(fake_remotes, "bundle.zip", data)
    _, written, failed, _, _ = remote.fetch_zip(
        bundle, ANNOTATION_FILES, AUDIO, str(tmp_path), requests.Session()
    )
    assert (
        written == ANNOTATION_FILES and failed == {}
    ), "every wanted file in the zip should be saved"
    assert file_contents(tmp_path, ANNOTATION_FILES) == file_contents(
        DATA_HOME, ANNOTATION_FILES
    ), "each file should be saved with the bytes it has in the zip"

    # Each audio file's bytes in the zip: from its header to the next file's header
    zf = zipfile.ZipFile(io.BytesIO(data))
    starts = sorted(m.header_offset for m in zf.infolist()) + [zf.start_dir]
    next_start = dict(zip(starts, starts[1:]))
    audio_spans = [
        (m.header_offset, next_start[m.header_offset])
        for m in zf.infolist()
        if m.filename in AUDIO
    ]
    asked = ranges(fake_remotes, "bundle.zip")

    def bytes_asked(start, end):
        return len(
            {
                b
                for first, last in asked
                for b in range(max(first, start), min(last + 1, end))
            }
        )

    assert None not in fake_remotes.gets(
        "bundle.zip"
    ), "a zip with audio should never be downloaded whole"
    assert not any(
        start <= first < end for first, _ in asked for start, end in audio_spans
    ), "no range request should start inside an audio file"
    assert all(
        bytes_asked(start, end) < end - start for start, end in audio_spans
    ), "no audio file should be downloaded"


# ------------------------------------------------------------------------ Tar


def test_fetch_tar_saves_only_matched_files(fake_remotes, tmp_path):
    bundle = serve(fake_remotes, "bundle.tar.gz", tar_bytes(track_by_track()))
    _, written, failed, _, _ = remote.fetch_tar(
        bundle, ANNOTATION_FILES, str(tmp_path), requests.Session()
    )
    assert (
        written == ANNOTATION_FILES and failed == {}
    ), "every wanted file in the tar should be saved"
    assert saved_files(tmp_path) == sorted(
        ANNOTATION_FILES
    ), "only the wanted files should be written, no audio"
    assert file_contents(tmp_path, ANNOTATION_FILES) == file_contents(
        DATA_HOME, ANNOTATION_FILES
    ), "each file should be saved with the bytes it has in the tar"


# ---------------------------------------------------------------------- fetch


def test_fetch_all_files_end_to_end(fake_remotes, tmp_path):
    fetched, missing, _, problems = fetch_fake(tmp_path)
    assert fetched == WANTED, "every wanted path should be fetched"
    assert missing == {}, "no wanted path should be missing"
    assert problems == [], "a run where every file is fetched needs no local run"
    assert saved_files(tmp_path) == sorted(
        WANTED
    ), "the files should be laid out like a local copy, with no audio"
    assert file_contents(tmp_path, WANTED) == file_contents(
        DATA_HOME, WANTED
    ), "each file should have the bytes of the local copy"


def test_fetch_archive_order_unknown_size_then_smallest(fake_remotes, tmp_path):
    beats = dataset_files("annotations")
    padding = b"\0" * 100_000  # makes an archive bigger, never wanted
    remotes = {
        "large": serve(
            fake_remotes,
            "large.zip",
            zip_bytes(
                {
                    "annotations/beats/track2.txt": beats[
                        "annotations/beats/track2.txt"
                    ],
                    "padding.bin": padding,
                },
                zipfile.ZIP_STORED,
            ),
        ),
        "small": serve(
            fake_remotes,
            "small.zip",
            zip_bytes(
                {"annotations/beats/track3.txt": beats["annotations/beats/track3.txt"]},
                zipfile.ZIP_STORED,
            ),
        ),
        "unknown": serve(
            fake_remotes,
            "unknown.zip",
            zip_bytes(
                {
                    "annotations/beats/track1.txt": beats[
                        "annotations/beats/track1.txt"
                    ],
                    "padding.bin": padding * 2,
                },
                zipfile.ZIP_STORED,
            ),
            failure="no length",
        ),
    }
    wanted = {
        "annotations/beats/track1.txt",
        "annotations/beats/track2.txt",
        "annotations/beats/track3.txt",
    }
    fetched, _, _, _ = remote.fetch(remotes, wanted, set(), str(tmp_path))
    opened = list(
        dict.fromkeys(
            name for method, name, _ in fake_remotes.requests if method == "GET"
        )
    )
    expected = ["unknown.zip", "small.zip", "large.zip"]
    assert fetched == wanted, "every wanted path should be fetched"
    assert (
        opened == expected
    ), "archives should be opened unknown size first, then smallest to largest"


def test_fetch_stops_opening_archives_when_done(fake_remotes, tmp_path):
    fetched, _, _, _ = fetch_fake(tmp_path)
    assert fetched == WANTED, "every wanted path should be fetched"
    assert (
        fake_remotes.gets("audio.zip") == []
    ), "once every wanted path is fetched, no other archive should be opened"


def test_fetch_after_budget_skips_remaining_remotes(fake_remotes, tmp_path):
    metadata_size = len(fake_remotes.files["metadata.csv"])
    # the plain file fits, the first read of an archive does not
    budget = remote.Budget(max_mb=(metadata_size + 10) / 1e6)
    _, _, sources, problems = fetch_fake(tmp_path, budget)
    audio_lines = [line for line in sources if "audio.zip" in line]
    assert (
        len(audio_lines) == 1 and "not read" in audio_lines[0]
    ), "a remote after the budget ran out should be logged as not read"
    assert (
        fake_remotes.gets("audio.zip") == []
    ), "a remote after the budget ran out should not be downloaded"
    assert len(problems) == 1 and problems[0].startswith(
        "remote limit"
    ), "the reason to run locally should be the remote limit"


# ------------------------------------------- fetch: the server or the files break


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


def break_truncated_tar(server):
    data = tar_bytes(dataset_files("annotations"))
    server.files["annotations.tar.gz"] = data[: len(data) // 2]
    annotations_remote = fake_dataset_loader.REMOTES["annotations"]
    annotations_remote.filename = "annotations.tar.gz"
    annotations_remote.url = server.url("annotations.tar.gz")
    # REMOTES lists the checksum of the whole tar, as uploaded
    annotations_remote.checksum = hashlib.md5(data).hexdigest()


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
        (break_truncated_tar, "annotations.tar.gz"),
        (break_metadata_404, "metadata.csv"),
    ],
    ids=lambda x: getattr(x, "__name__", x).removeprefix("break_"),
)
def test_fetch_unreadable_remote(fake_remotes, tmp_path, break_remote, name):
    break_remote(fake_remotes)
    _, _, _, problems = fetch_fake(tmp_path)
    assert problems, "a remote that cannot be read should need a local run"
    named = any(name in problem for problem in problems)
    assert named, "the reason should name the remote that could not be read"


@pytest.mark.parametrize("mode", ["no length", "ignore range"])
def test_fetch_no_range_support(fake_remotes, tmp_path, mode):
    fake_remotes.failures["annotations.zip"] = mode
    fetched, _, _, problems = fetch_fake(tmp_path)
    assert None in fake_remotes.gets(
        "annotations.zip"
    ), f"a zip on a server with {mode} should be downloaded whole"
    assert (
        fetched == WANTED and problems == []
    ), f"a server with {mode} should still give every wanted path"


def test_fetch_rate_limit(fake_remotes, tmp_path, waits):
    fake_remotes.failures["annotations.zip"] = "429 once"
    fetched, _, _, problems = fetch_fake(tmp_path)
    assert waits and waits[0] >= 3, "a 429 should wait as long as Retry-After asks"
    assert (
        fetched == WANTED and problems == []
    ), "after the wait, the retry should succeed"


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
def test_fetch_zip_layout(
    fake_remotes, tmp_path, prefix, unpack_directories, destination_dir
):
    files = dataset_files("annotations")  # annotations/beats/track1.txt, ...
    inside = {prefix + p.removeprefix("annotations/"): d for p, d in files.items()}
    fake_remotes.files["annotations.zip"] = zip_bytes(inside)
    annotations_remote = fake_dataset_loader.REMOTES["annotations"]
    annotations_remote.unpack_directories = unpack_directories
    annotations_remote.destination_dir = destination_dir
    fetched, _, _, problems = fetch_fake(tmp_path)
    assert (
        fetched == WANTED and problems == []
    ), "zip files should be matched to index paths the way mirdata unpacks the zip"
    assert file_contents(tmp_path, ANNOTATION_FILES) == file_contents(
        DATA_HOME, ANNOTATION_FILES
    ), "each file should be saved at its index path"
