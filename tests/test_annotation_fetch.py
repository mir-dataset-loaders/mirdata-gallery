"""Tests for scripts/annotation_fetch.py: which files are wanted, and fetching them."""

import zipfile

import pytest

import annotation_fetch
from audio_fakes import FakeRangeSession, FakeResponse, fake_remote, zip_bytes

URL = "https://example.test/all.zip"

INDEX = {
    "tracks": {
        "a": {
            "audio": ["audio/a.wav", "x"],
            "beats": ["annotations/beats/a.csv", "x"],
            "chords": ["annotations/chords/a.csv", "x"],
        },
        "b": {
            "audio_mix": ["audio/b.wav", "x"],
            "beats": ["annotations/beats/b.csv", "x"],
            "chords": [None, None],  # an annotation this track does not have
        },
    },
    "multitracks": {"m": {"audio_stem": ["audio/m.wav", "x"], "notes": ["annotations/m.mid", "x"]}},
    "metadata": {"meta": ["metadata.csv", "x"], "missing": [None, None]},
}

FILES = {
    "audio/a.wav": b"RIFF" + b"\0" * 1000,
    "annotations/beats/a.csv": b"0.5;1\n1.0;2\n",
    "annotations/chords/a.csv": b"0.0;1.0;C:maj\n",
    "annotations/beats/b.csv": b"0.4;1\n",
    "annotations/m.mid": b"MThd",
    "metadata.csv": b"id;tempo\na;120\n",
}


class PlainSession:
    """A server without range support: HEAD gives no size, GET streams the whole body."""

    def __init__(self, blobs):
        self.blobs = blobs
        self.calls = []

    def mount(self, prefix, adapter):
        pass

    def request(self, method, url, timeout, **kwargs):
        self.calls.append((method, url, kwargs))
        response = FakeResponse(200, content=self.blobs[url] if method == "GET" else b"", url=url)
        response.iter_content = lambda size: (
            response.content[i : i + size] for i in range(0, len(response.content), size)
        )
        return response


@pytest.fixture
def use_session(monkeypatch):
    def use(session):
        monkeypatch.setattr(annotation_fetch.requests, "Session", lambda: session)
        return session

    return use


def wanted():
    return annotation_fetch.annotation_paths(INDEX)


# ------------------------------------------------------------ wanted paths


def test_annotation_paths_skips_audio_and_keeps_metadata():
    assert wanted() == {
        "annotations/beats/a.csv",
        "annotations/chords/a.csv",
        "annotations/beats/b.csv",
        "annotations/m.mid",
        "metadata.csv",
    }


def test_annotation_paths_limited_to_some_tracks():
    assert annotation_fetch.annotation_paths(INDEX, ["b"]) == {
        "annotations/beats/b.csv",
        "annotations/m.mid",
        "metadata.csv",
    }


def test_annotation_paths_of_empty_index():
    assert annotation_fetch.annotation_paths({}) == set()


# -------------------------------------------------------------- fetching


def test_big_zip_is_read_by_range(tmp_path, use_session, monkeypatch):
    monkeypatch.setattr(annotation_fetch, "MAX_ARCHIVE_MB", 0)  # treat the zip as big
    session = use_session(FakeRangeSession({URL: zip_bytes(FILES, prefix="bundle/")}))

    fetched, errors, sources = annotation_fetch.fetch(
        {"all": fake_remote("all.zip", URL)}, wanted(), str(tmp_path)
    )

    assert fetched == wanted()
    assert errors == {}
    for path in wanted():
        assert (tmp_path / path).read_bytes() == FILES[path]
    assert not (tmp_path / "audio").exists()  # the audio is never fetched
    gets = [call for call in session.calls if call[0] == "GET"]
    assert all("Range" in call[2]["headers"] for call in gets)
    assert "5 matched, 5 fetched" in sources[0]
    assert "requests" in sources[0]


def test_small_zip_is_downloaded_whole_in_one_request(tmp_path, use_session):
    session = use_session(FakeRangeSession({URL: zip_bytes(FILES)}))
    fetched, errors, sources = annotation_fetch.fetch(
        {"all": fake_remote("all.zip", URL)}, wanted(), str(tmp_path)
    )
    assert fetched == wanted()
    assert len([call for call in session.calls if call[0] == "GET"]) == 1
    assert "downloaded whole" in sources[0]


def test_zip_without_range_support_is_downloaded_whole(tmp_path, use_session):
    use_session(PlainSession({URL: zip_bytes(FILES, compression=zipfile.ZIP_STORED)}))
    fetched, errors, sources = annotation_fetch.fetch(
        {"all": fake_remote("all.zip", URL)}, wanted(), str(tmp_path)
    )
    assert fetched == wanted()
    assert (tmp_path / "metadata.csv").read_bytes() == FILES["metadata.csv"]


def test_zip_without_range_support_over_the_cap_is_not_downloaded(tmp_path, use_session, monkeypatch):
    monkeypatch.setattr(annotation_fetch, "MAX_ARCHIVE_MB", 1e-6)
    use_session(PlainSession({URL: zip_bytes(FILES)}))
    fetched, errors, sources = annotation_fetch.fetch(
        {"all": fake_remote("all.zip", URL)}, wanted(), str(tmp_path)
    )
    assert fetched == set()
    assert "not downloaded whole" in sources[0]
    assert set(errors) == wanted()  # every wanted file is accounted for


def test_destination_dir_is_part_of_the_index_path(tmp_path, use_session):
    use_session(FakeRangeSession({URL: zip_bytes({"beats/a.csv": b"1"})}))
    index = {"tracks": {"a": {"beats": ["annotations/beats/a.csv", "x"]}}}
    fetched, errors, _ = annotation_fetch.fetch(
        {"ann": fake_remote("ann.zip", URL, destination_dir="annotations")},
        annotation_fetch.annotation_paths(index),
        str(tmp_path),
    )
    assert fetched == {"annotations/beats/a.csv"}


def test_file_over_the_size_limit_is_skipped(tmp_path, use_session):
    use_session(FakeRangeSession({URL: zip_bytes(FILES)}))
    fetched, errors, _ = annotation_fetch.fetch(
        {"all": fake_remote("all.zip", URL)}, wanted(), str(tmp_path), max_file_mb=1e-5
    )
    big = {p for p in wanted() if len(FILES[p]) > 10}
    assert big and fetched == wanted() - big
    assert all("over the" in errors[p] for p in big)


def test_plain_file_remote_listed_in_the_index_is_fetched(tmp_path, use_session):
    url = "https://example.test/metadata.csv"
    use_session(FakeRangeSession({url: FILES["metadata.csv"]}))
    fetched, errors, sources = annotation_fetch.fetch(
        {"meta": fake_remote("metadata.csv", url)}, {"metadata.csv"}, str(tmp_path)
    )
    assert fetched == {"metadata.csv"}
    assert (tmp_path / "metadata.csv").read_bytes() == FILES["metadata.csv"]


def test_other_remotes_are_reported_not_fetched(tmp_path, use_session):
    session = use_session(FakeRangeSession({}))
    remotes = {
        "tar": fake_remote("all.tar.gz", "https://example.test/all.tar.gz"),
        "pdf": fake_remote("paper.pdf", "https://example.test/paper.pdf"),
    }
    fetched, errors, sources = annotation_fetch.fetch(remotes, wanted(), str(tmp_path))
    assert fetched == set()
    assert "not a zip, skipped" in sources[0]
    assert "not an annotation file of the index" in sources[1]
    assert all(why == "not in any readable remote" for why in errors.values())
    assert session.calls == []


def test_unreachable_remote_is_reported(tmp_path, use_session):
    class Down(FakeRangeSession):
        def request(self, method, url, timeout, **kwargs):
            return FakeResponse(404, url=url)

    use_session(Down({}))
    fetched, errors, sources = annotation_fetch.fetch(
        {"all": fake_remote("all.zip", URL)}, wanted(), str(tmp_path)
    )
    assert fetched == set()
    assert "HTTP 404" in sources[0]


def test_files_already_on_disk_are_kept(tmp_path, use_session):
    for path in wanted():
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_bytes(b"cached")
    session = use_session(FakeRangeSession({URL: zip_bytes(FILES)}))
    fetched, errors, sources = annotation_fetch.fetch(
        {"all": fake_remote("all.zip", URL)}, wanted(), str(tmp_path)
    )
    assert fetched == wanted()
    assert session.calls == []
    assert "5 files already in" in sources[0]


def test_no_remotes(tmp_path):
    fetched, errors, sources = annotation_fetch.fetch({}, wanted(), str(tmp_path))
    assert fetched == set()
    assert "no remotes" in sources[0]
    assert set(errors) == wanted()
