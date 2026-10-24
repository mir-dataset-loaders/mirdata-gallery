"""card_utils.py: the card's YAML form and the index checksum."""

import yaml

import card_utils


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
        "stats": {
            "computed": {"mode": "local", "index": "abc"},
            "audio": {"status": "ok", "problems": [], "n_tracks": 2},
            "annotations": {"beats": {"tempo_from_beats": {"unit": "s", "edges": [1, 2, 3], "counts": [4, 5]}}},
        },
    }
    path = tmp_path / "fake.yaml"
    card_utils.write_card(str(path), card)
    text = path.read_text()
    assert "edges: [1, 2, 3]" in text
    assert "counts: [4, 5]" in text
    assert "- BeatData\n" in text  # lists of strings keep the block style
    assert "problems: []" in text
    assert yaml.safe_load(text) == card
