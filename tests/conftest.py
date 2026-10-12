"""Shared fixtures: a fake mirdata-style dataset on disk and as a zip."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from audio_fakes import make_flac, make_mp3_cbr, make_wav, zip_bytes

RESOURCES = Path(__file__).parent / "resources" / "audio_stats"


@pytest.fixture
def fake_index():
    with open(RESOURCES / "fake_index.json", encoding="utf-8") as file:
        return json.load(file)


@pytest.fixture
def fake_dataset(tmp_path, fake_index):
    data_home = tmp_path / "mir_datasets" / "fake_audio_stats"
    audio_files = {
        "audio/a.wav": make_wav(1.0, 8000),
        "audio/b.flac": make_flac(2.5, 16000),
        "audio/c.mp3": make_mp3_cbr(3.0),
        "audio/d.wav": make_wav(4.0, 8000),
        "audio/bad.wav": b"this is not a WAV file",
    }

    for relative_path, data in audio_files.items():
        path = data_home / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    index_path = tmp_path / "fake_index.json"
    index_path.write_text(json.dumps(fake_index), encoding="utf-8")

    archive = zip_bytes(audio_files, prefix="bundle/")
    archive_path = tmp_path / "fake_audio.zip"
    archive_path.write_bytes(archive)

    return SimpleNamespace(
        index=fake_index,
        index_path=index_path,
        data_home=data_home,
        audio_files=audio_files,
        archive=archive,
        archive_path=archive_path,
    )
