"""Tests for scripts/stats/to_card.py (the card's stats field) and its YAML form (cards_io.py)."""

import pytest
import yaml

import cards_io
from stats.to_card import card_stats, index_fingerprint

HIST = {"unit": "s", "edges": [1, 2, 3], "counts": [4, 5]}

AUDIO = {
    "status": "ok",
    "problems": [],
    "n_tracks": 2,
    "n_tracks_with_audio": 2,
    "n_tracks_counted": 2,
    "total_seconds": 3.0,
    "duration_histogram": HIST,
    "sample_rate": 8000,
    "sample_rates": {"8000": 2},  # as after a JSON round trip
    "n_audio_files": 2,
    "n_audio_files_counted": 2,
    "all_files_seconds": 3.0,
    "errors": {"audio/x.wav": "bad header"},
    "sources": ["  all  all.zip  ..."],
}
ANNOTATIONS = {
    "status": "incomplete",
    "problems": [],
    "n_tracks": 2,
    "n_tracks_loaded": 2,
    "tracks_with": {"BeatData": 2},
    "annotations": {
        "beats": {"type": "BeatData", "n_tracks": 2, "n_annotations": 2, "beats_per_bar": {"4": 2}, "tempo": HIST},
        "melody": {
            "type": "F0Data",
            "n_tracks": 2,
            "n_annotations": 2,
            "f0_median_per_annotation": HIST,
            "voiced_fraction": None,
        },
    },
    "skipped": {"tempo": "not a mirdata TempoData object (got str)"},
    "errors": {},
    "annotation_errors": {"chords": {"n_tracks": 1, "examples": {"a": "ValueError: x"}}},
    "missing_files": {"ann/b.txt": "not in any readable remote"},
    "sources": ["  local  /data"],
}


def test_card_stats_keeps_numbers_and_drops_logs():
    stats = card_stats({"name": "fake", "audio": AUDIO, "annotations": ANNOTATIONS}, "remote", "abc", "2026-10-12")
    assert stats["computed"] == {"mode": "remote", "index": "abc", "date": "2026-10-12"}
    audio = stats["audio"]
    assert "sources" not in audio and "errors" not in audio
    assert audio["n_errors"] == 1
    assert audio["duration_histogram"] == HIST
    assert audio["sample_rates"] == {8000: 2}  # number keys, as numbers
    ann = stats["annotations"]
    assert "sources" not in ann and "missing_files" not in ann
    assert ann["n_missing_files"] == 1
    assert ann["n_track_errors"] == 0
    assert ann["annotation_errors"] == {"chords": 1}
    assert ann["annotations"]["beats"]["beats_per_bar"] == {4: 2}
    assert ann["annotations"]["melody"] == ANNOTATIONS["annotations"]["melody"]  # copied as is
    assert ann["skipped"] == ANNOTATIONS["skipped"]


def test_card_stats_with_one_part_only():
    stats = card_stats({"name": "fake", "audio": AUDIO}, "local", "abc", "2026-10-12")
    assert sorted(stats) == ["audio", "computed"]


def test_error_parts_and_loader_errors():
    stats = card_stats(
        {"name": "fake", "audio": {"status": "error", "error": "RuntimeError: x"}, "annotations": ANNOTATIONS},
        "remote", "abc", "2026-10-12",
    )
    assert stats["audio"] == {"status": "error", "error": "RuntimeError: x"}
    stats = card_stats({"name": "fake", "error": "ImportError: y"}, "remote", "abc", "2026-10-12")
    assert stats == {"computed": {"mode": "remote", "index": "abc", "date": "2026-10-12"}, "error": "ImportError: y"}


def test_date_defaults_to_today_and_mode_is_checked():
    assert len(card_stats({"name": "f", "audio": AUDIO}, "local", "abc")["computed"]["date"]) == 10
    with pytest.raises(ValueError, match="mode"):
        card_stats({"name": "f"}, "cloud", "abc")


def test_index_fingerprint_is_the_published_checksum(tmp_path):
    from types import SimpleNamespace

    remote = SimpleNamespace(checksum="c7f5f853768815885cea70d6c246895d")
    ds = SimpleNamespace(_index_data=SimpleNamespace(remote=remote), index_path=str(tmp_path / "missing.json"))
    assert index_fingerprint(ds) == "c7f5f85376881588"  # no download needed


def test_index_fingerprint_without_remote_hashes_the_file(tmp_path):
    from types import SimpleNamespace

    path = tmp_path / "index.json"
    path.write_text('{"tracks": {}}')
    ds = SimpleNamespace(_index_data=SimpleNamespace(remote=None), index_path=str(path))
    first = index_fingerprint(ds)
    assert len(first) == 16 and first == index_fingerprint(ds)
    path.write_text('{"tracks": {"a": {}}}')
    assert index_fingerprint(ds) != first


def test_real_fingerprint_does_not_download():
    import mirdata

    ds = mirdata.initialize("acousticbrainz_genre")  # its index is 334 MB, never fetched here
    assert len(index_fingerprint(ds)) == 16


def test_number_lists_go_on_one_line_and_round_trip(tmp_path):
    card = {
        "name": "fake",
        "annotations": ["BeatData", "ChordData"],
        "stats": card_stats({"name": "fake", "audio": AUDIO, "annotations": ANNOTATIONS}, "local", "abc", "2026-10-12"),
    }
    path = tmp_path / "fake.yaml"
    cards_io.write_card(str(path), card)
    text = path.read_text()
    assert "edges: [1, 2, 3]" in text
    assert "counts: [4, 5]" in text
    assert "- BeatData\n" in text  # lists of strings keep the block style
    assert "problems: []" in text
    assert "date: '2026-10-12'" in text  # stays a string, not a YAML date
    assert yaml.safe_load(text) == card
