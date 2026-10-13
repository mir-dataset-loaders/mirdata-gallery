"""compute_stats.py on the fake dataset: what is left on disk after a remote run.

The annotation files are fetched into a temporary folder that is deleted at
the end of the run, unless --fetch-dir names a folder to keep them in.
"""

import json
import tempfile

import compute_stats
from conftest import files_under

ANNOTATION_FILES = [
    "annotations/beats/track1.txt",
    "annotations/beats/track2.txt",
    "annotations/beats/track3.txt",
    "annotations/chords/track1.lab",
    "annotations/chords/track2.lab",
]


def test_fetched_files_are_deleted_after_the_run(fake_remotes, tmp_path, monkeypatch, capsys):
    temp = tmp_path / "temp"  # the system's temporary folder, for this test
    temp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(temp))
    compute_stats.main(["--dataset", "fake_dataset", "--json"])
    result = json.loads(capsys.readouterr().out)["fake_dataset"]
    assert result["annotations"]["status"] == "ok"  # the files were fetched and read...
    assert files_under(temp) == []  # ...and nothing is left of them


def test_fetch_dir_keeps_the_fetched_files(fake_remotes, tmp_path):
    kept = tmp_path / "kept"
    compute_stats.main(["--dataset", "fake_dataset", "--fetch-dir", str(kept)])
    assert files_under(kept / "fake_dataset") == ANNOTATION_FILES
