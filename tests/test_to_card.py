"""Tests for scripts/stats/to_card.py (the card's stats field) and its YAML form and index checksum (card_utils.py)."""

import pytest
import yaml

import card_utils
from stats.to_card import result_to_card_stats

HIST = {"unit": "s", "edges": [1, 2, 3], "counts": [4, 5]}

AUDIO = {"name": "fake", "status": "ok", "problems": [], "n_tracks": 2, "n_audio_files": 4}
ANNOTATIONS = {
    "status": "incomplete",
    "problems": [],
    "n_tracks": 2,
    "n_tracks_loaded": 2,
    "tracks_with": {"BeatData": 2},
    "annotations": {
        "beats": {"type": "BeatData", "n_tracks": 2, "n_annotations": 2, "meter": {"4": 2}, "tempo_from_beats": HIST},
        "melody": {
            "type": "F0Data",
            "n_tracks": 2,
            "n_annotations": 2,
            "frequencies": None,
        },
        "pitches": {"type": "MultiF0Data", "n_tracks": 2, "n_annotations": 2, "frequencies": HIST, "polyphony": {"1": 9, "2": 4}},
    },
    "skipped": {"tempo": "not a mirdata TempoData object (got str)"},
    "errors": {},
    "annotation_errors": {"chords": {"n_tracks": 1, "examples": {"a": "ValueError: x"}}},
    "missing_files": {"ann/b.txt": "not in any readable remote"},
    "sources": ["  local  /data"],
}


def test_card_stats_keeps_numbers_and_drops_logs():
    stats = result_to_card_stats({"name": "fake", "audio": AUDIO, "annotations": ANNOTATIONS}, "remote", "abc")
    assert stats["computed"] == {"mode": "remote", "index": "abc"}
    assert stats["audio"] == {"status": "ok", "problems": [], "n_tracks": 2, "n_audio_files": 4}
    ann = stats["annotations"]
    assert "sources" not in ann and "missing_files" not in ann
    assert ann["n_missing_files"] == 1
    assert ann["n_track_errors"] == 0
    assert ann["annotation_errors"] == {"chords": 1}
    assert ann["annotations"]["beats"]["meter"] == {4: 2}
    assert ann["annotations"]["pitches"]["polyphony"] == {1: 9, 2: 4}
    assert ann["annotations"]["melody"] == ANNOTATIONS["annotations"]["melody"]  # copied as is
    assert ann["skipped"] == ANNOTATIONS["skipped"]


def test_card_stats_with_one_part_only():
    stats = result_to_card_stats({"name": "fake", "audio": AUDIO}, "local", "abc")
    assert sorted(stats) == ["audio", "computed"]


def test_error_parts_and_loader_errors():
    stats = result_to_card_stats(
        {"name": "fake", "audio": {"status": "error", "error": "RuntimeError: x"}, "annotations": ANNOTATIONS},
        "remote", "abc",
    )
    assert stats["audio"] == {"status": "error", "error": "RuntimeError: x"}
    stats = result_to_card_stats({"name": "fake", "error": "ImportError: y"}, "remote", "abc")
    assert stats == {"computed": {"mode": "remote", "index": "abc"}, "error": "ImportError: y"}


def test_mode_is_checked():
    with pytest.raises(ValueError, match="mode"):
        result_to_card_stats({"name": "f"}, "cloud", "abc")


def test_index_checksum_is_the_published_checksum(tmp_path):
    from types import SimpleNamespace

    remote = SimpleNamespace(checksum="c7f5f853768815885cea70d6c246895d")
    ds = SimpleNamespace(_index_data=SimpleNamespace(remote=remote), index_path=str(tmp_path / "missing.json"))
    assert card_utils.index_checksum(ds) == "c7f5f853768815885cea70d6c246895d"  # no download needed


def test_real_checksum_does_not_download():
    import mirdata

    ds = mirdata.initialize("acousticbrainz_genre")  # its index is 334 MB, never fetched here
    assert card_utils.index_checksum(ds) == ds._index_data.remote.checksum


def test_number_lists_go_on_one_line_and_round_trip(tmp_path):
    card = {
        "name": "fake",
        "annotations": ["BeatData", "ChordData"],
        "stats": result_to_card_stats({"name": "fake", "audio": AUDIO, "annotations": ANNOTATIONS}, "local", "abc"),
    }
    path = tmp_path / "fake.yaml"
    card_utils.write_card(str(path), card)
    text = path.read_text()
    assert "edges: [1, 2, 3]" in text
    assert "counts: [4, 5]" in text
    assert "- BeatData\n" in text  # lists of strings keep the block style
    assert "problems: []" in text
    assert yaml.safe_load(text) == card
