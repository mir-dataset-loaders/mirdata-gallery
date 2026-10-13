"""Remote mode (the default): the stats of the fake dataset, read from its zips on a local server.

The server serves audio.zip and annotations.zip (conftest.py, fake_remotes).
A remote run must give exactly the numbers of a local run.
"""

from conftest import files_under
from fake_dataset import DATA_HOME
from stats import dataset
from stats.annotations import remote_files


def without_sources(part):
    """A part's result without its log lines, which name where the files came from."""
    return {k: v for k, v in part.items() if k != "sources"}


def test_remote_stats_equal_local_stats(fake_remotes, tmp_path):
    remote = dataset.compute("fake_dataset", str(tmp_path))
    local = dataset.compute("fake_dataset", DATA_HOME, local=True)
    for part in ("audio", "annotations"):
        assert remote[part]["status"] == "ok"
        assert without_sources(remote[part]) == without_sources(local[part])


def test_small_zip_is_downloaded_whole(fake_remotes, tmp_path):
    """A zip up to 200 MB comes in one piece: fewer requests than the 5 files it holds."""
    dataset.compute("fake_dataset", str(tmp_path), parts=["annotations"])
    assert len(fake_remotes.gets("annotations.zip")) < 5


def test_big_zip_is_read_by_range(fake_remotes, tmp_path, monkeypatch):
    monkeypatch.setattr(remote_files, "MAX_ARCHIVE_MB", 0)  # every zip counts as big
    remote = dataset.compute("fake_dataset", str(tmp_path), parts=["annotations"])
    local = dataset.compute("fake_dataset", DATA_HOME, local=True, parts=["annotations"])
    assert remote["annotations"]["status"] == "ok"
    assert without_sources(remote["annotations"]) == without_sources(local["annotations"])
    assert len(fake_remotes.gets("annotations.zip")) > 1
    assert all(fake_remotes.gets("annotations.zip"))  # every request is a range


def test_only_annotation_files_are_saved(fake_remotes, tmp_path):
    """The fetch folder gets the 5 annotation files and no audio (the audio part reads headers only).

    compute() leaves them there; the commands delete the folder after the run (test_compute_stats.py).
    """
    dataset.compute("fake_dataset", str(tmp_path))
    assert files_under(tmp_path) == [
        "annotations/beats/track1.txt",
        "annotations/beats/track2.txt",
        "annotations/beats/track3.txt",
        "annotations/chords/track1.lab",
        "annotations/chords/track2.lab",
    ]
