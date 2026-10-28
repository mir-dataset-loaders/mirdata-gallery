"""The Stat classes of stats/annotation_types.py, fed mirdata annotations built in code.

Numeric fields are compared with grid() of the values a Stat should collect;
the exact bins are checked by hand only in test_grid*.
"""

import numpy as np
from mirdata import annotations

from stats.annotation_types import (
    F0,
    Beats,
    Chords,
    Events,
    Keys,
    Lyrics,
    MultiF0,
    Notes,
    Sections,
    Tempo,
    grid,
    is_empty,
)


def intervals(*pairs):
    return np.array(pairs, dtype=float)


def beats(times, positions=None, time_unit="s", position_unit="bar_index"):
    if positions is None:
        return annotations.BeatData(np.array(times, dtype=float), time_unit, None, None)
    return annotations.BeatData(
        np.array(times, dtype=float), time_unit, np.array(positions), position_unit
    )


def events(*labels):
    return annotations.EventData(
        intervals(*[(i, i + 1) for i in range(len(labels))]), "s", list(labels), "open"
    )


def collect(stat, *values):
    """The Stat after reading one value per track."""
    for value in values:
        stat.add(value)
    return stat


# ---------------------------------------------------------------- one Stat each


def test_tempo():
    track1 = annotations.TempoData(intervals((0, 10)), "s", np.array([120.0]), "bpm")
    track2 = annotations.TempoData(
        intervals((0, 10), (10, 20)), "s", np.array([90.0, 180.0]), "bpm"
    )
    result = collect(Tempo(), track1, track2).result()
    expected = {"tempo": grid([120.0, 90.0, 180.0], "bpm")}
    assert (
        result == expected
    ), "every tempo of every annotation should be counted on one 1-bpm grid"


def test_beats():
    every_half_second = [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5]
    bars_of_4 = [1, 2, 3, 4, 1, 2, 3, 4, 1, 2]  # two bars of 4, then 2 beats of a third
    in_ms = beats([0, 1000, 2000, 3000, 4000, 5000], [1, 2, 3, 1, 2, 3], time_unit="ms")
    result = collect(
        Beats(),
        beats(every_half_second, bars_of_4),  # 120 bpm, meter 4
        in_ms,  # 60 bpm, meter 3
        beats([0, 0.25, 0.5], [1, 2, 3], position_unit="global_index"),  # 240 bpm
        beats([0.0]),  # one beat
        beats([0, 1, 2], time_unit="ticks"),
    ).result()
    tempo = grid([120.0, 60.0, 240.0], "bpm")
    assert result["tempo_from_beats"] == tempo, (
        "tempo should be 60 / the median beat gap, one per annotation, with ms read as s/1000;"
        " one beat or a non-clock unit (ticks) should give no tempo"
    )
    assert result["meter"] == {3: 1, 4: 1}, (
        "meter should be each track's most common bar length (a short last bar does not"
        " change it); positions that are not bar_index should give no meter"
    )


def test_chords():
    track1 = annotations.ChordData(
        intervals((0, 1), (1, 2), (2, 3)), "s", ["C:maj", "A:min", "C:maj"], "harte"
    )
    track2 = annotations.ChordData(
        intervals((0, 1), (1, 2), (2, 3)), "s", ["G:7", "N", "C"], "harte"
    )
    result = collect(Chords(), track1, track2).result()
    labels = {"C:maj": 2, "A:min": 1, "G:7": 1, "N": 1, "C": 1}
    assert (
        result["labels"] == labels
    ), "labels should count every chord label of every track"
    qualities = {"maj": 3, "min": 1, "7": 1, "N": 1}
    assert (
        result["qualities"] == qualities
    ), "qualities should count the quality of every label"


def test_f0():
    times = np.array([0.0, 0.01, 0.02])
    binary = annotations.F0Data(
        times,
        "s",
        np.array([440.0, 440.0, 880.0]),
        "hz",
        np.array([1.0, 0.0, 1.0]),
        "binary",
    )
    likelihood = annotations.F0Data(
        times[:2],
        "s",
        np.array([93.0, 93.0]),  # A6 = 1760 Hz
        "midi",
        np.array([0.9, 0.2]),
        "likelihood",
    )
    result = collect(F0(), binary, likelihood).result()
    expected = {"frequencies": grid([440.0, 880.0, 1760.0], "hz")}
    assert result == expected, (
        "only voiced frames should count (binary voicing above 0, likelihood from 0.5),"
        " in Hz, whatever unit the loader gives"
    )


def test_multif0():
    track1 = annotations.MultiF0Data(
        np.array([0.0, 0.01, 0.02, 0.03]),
        "s",
        [[440.0], [440.0, 880.0], [], [0.0]],
        "hz",
    )
    track2 = annotations.MultiF0Data(
        np.array([0.0, 0.01]), "s", [[57.0, 69.0, 81.0], [69.0]], "midi"
    )  # 220, 440, 880 Hz
    result = collect(MultiF0(), track1, track2).result()
    frequencies = grid([440.0, 440.0, 880.0, 220.0, 440.0, 880.0, 440.0], "hz")
    assert (
        result["frequencies"] == frequencies
    ), "every sounding pitch should be counted on one Hz grid, whatever unit the loader gives"
    polyphony = {1: 2, 2: 1, 3: 1}
    assert result["polyphony"] == polyphony, (
        "polyphony should count frames per number of pitches sounding at once;"
        " silent frames (no pitch, or only 0 Hz) are left out"
    )


def test_notes():
    two_notes = intervals((0, 1), (1, 2))
    in_midi = annotations.NoteData(two_notes, "s", np.array([64.0, 65.98]), "midi")
    result = collect(Notes(), in_midi, in_midi).result()
    expected = {"pitches": grid([64, 64, 66, 66], "midi")}
    assert result == expected, (
        "MIDI pitches should be counted per note, rounded to the nearest one (65.98 as 66,"
        " not 65)"
    )

    in_hz = annotations.NoteData(two_notes, "s", np.array([440.0, 0.0]), "hz")  # 0: no pitch
    higher = annotations.NoteData(two_notes, "s", np.array([880.0, 1760.0]), "hz")
    result = collect(Notes(), in_hz, higher).result()
    expected = {"pitches": grid([440.0, 880.0, 1760.0], "hz")}
    assert result == expected, "Hz pitches should be counted in Hz, without the 0s (no pitch)"


def test_sections():
    track1 = annotations.SectionData(
        intervals((0, 10), (10, 30)), "s", ["verse", "chorus"], "open"
    )
    track2 = annotations.SectionData(intervals((0, 5000)), "ms", ["verse"], "open")
    track3 = annotations.SectionData(intervals((0, 40)), "s")  # no labels
    result = collect(Sections(), track1, track2, track3).result()
    labels = {"verse": 2, "chorus": 1}
    assert (
        result["labels"] == labels
    ), "labels should count every section label; unlabeled sections add none"
    lengths = grid([10.0, 20.0, 5.0, 40.0], "s")
    assert result["section_interval_seconds"] == lengths, (
        "every section's length in seconds (ms read as s/1000), labeled or not,"
        " should be counted on one 1 s grid"
    )


def test_keys():
    track1 = annotations.KeyData(
        intervals((0, 10), (10, 20)), "s", ["C:major", "A:minor"], "key_mode"
    )
    track2 = annotations.KeyData(
        intervals((0, 10), (10, 20)), "s", ["C:major", "C"], "key_mode"
    )
    result = collect(Keys(), track1, track2).result()
    keys = {"C:major": 2, "A:minor": 1, "C": 1}
    assert result["keys"] == keys, "keys should count every key label"
    modes = {"major": 2, "minor": 1, "(none)": 1}
    assert (
        result["modes"] == modes
    ), "modes should count the part after the colon; a key without one is (none)"


def test_lyrics():
    def lyrics(*words, unit="words"):
        return annotations.LyricData(
            intervals(*[(i, i + 1) for i in range(len(words))]), "s", list(words), unit
        )

    two_singers = {"lead": lyrics("la", "la", "la"), "backing": lyrics("oh", "oh")}
    syllables = lyrics("ba", "na", "na", "na", unit="syllable_open")
    result = collect(Lyrics(), two_singers, syllables).result()
    units = {"words": 2, "syllable_open": 1}
    assert (
        result["lyric_unit"] == units
    ), "lyric_unit should count the annotations of each unit"
    per_track = grid([5, 4], "words")
    assert result["lyrics_per_track"] == per_track, (
        "lyrics_per_track should add up all of a track's annotations,"
        " in the most common unit"
    )


def test_events():
    result = collect(Events(), events("kick", "snare"), events("kick")).result()
    expected = {"events": {"kick": 2, "snare": 1}}
    assert result == expected, "events should count every event label"


def test_every_label_is_kept():
    rare = [f"event{i}" for i in range(40)]
    result = collect(Events(), events(*rare, "kick", "kick", "kick")).result()
    assert len(result["events"]) == 41, "every label should be kept, however many there are"
    assert "(other)" not in result["events"], "no labels should be folded into (other)"
    assert list(result["events"])[0] == "kick", "labels should come most common first"


# ------------------------------------------------------------ the shared base


def test_stat_add():
    stat = Events()
    assert stat.add(events("kick")) is True, "a mirdata annotation should be used"
    assert (
        stat.add({"left": events("kick"), "right": events("snare")}) is True
    ), "a dict of annotations should be used"
    two_annotators = annotations.MultiAnnotator(
        ["ann1", "ann2"], [events("kick"), events("kick")], annotations.EventData
    )
    assert stat.add(two_annotators) is True, "a MultiAnnotator should be used"
    assert (
        stat.add([events("hat"), events("hat")]) is True
    ), "a list of annotations should be used"
    assert (
        stat.add("kick") is False
    ), "a value that is not a mirdata annotation should not be used"
    assert (
        stat.add(events("kick").events) is False
    ), "a plain list of labels should not be used"

    summary = stat.summary()
    assert (
        summary["n_tracks"] == 4
    ), "each track should count once, however many annotations it has"
    assert (
        summary["n_annotations"] == 7
    ), "every annotation inside a dict, list or MultiAnnotator should count"
    parts = {"left": 1, "right": 1, "ann1": 1, "ann2": 1}
    assert (
        summary["parts"] == parts
    ), "dict keys and annotator names should be counted as parts; lists have none"


def test_is_empty():
    for nothing in (None, "", "  ", [], {}, (), {"left": None}):
        assert is_empty(nothing), f"{nothing!r} should count as no annotation"
    for something in (events("kick"), {"left": events("kick")}, [events("kick")]):
        assert not is_empty(something), f"{something!r} should count as an annotation"


# ------------------------------------------------------------------ helpers


def test_chord_quality():
    expected = {
        "N": "N",
        "X": "X",
        "C": "maj",
        "C:maj": "maj",
        "A:min": "min",
        "C:min7/3": "min7",
        "C:maj(9)": "maj",
        "G:7": "7",
    }
    for label, quality in expected.items():
        assert Chords.chord_quality(label) == quality, f"{label} should have quality {quality}"


def test_bar_lengths():
    bars = Beats.bar_lengths([1, 2, 3, 4, 1, 2, 3])
    assert bars == [4, 3], "a bar should end where the count goes back down"
    bars = Beats.bar_lengths([0, 0, 1, 2, 1, 2])
    assert bars == [2, 2], "position 0 (a beat outside any bar) should be skipped"
    assert Beats.bar_lengths([]) == [], "no positions should give no bars"


def test_grid():
    result = grid([133.7, 101.9, 133.2, 120.0, 133.0], "bpm")
    expected = {"unit": "bpm", "width": 1, "counts": {101: 1, 120: 1, 133: 3}}
    assert result == expected, (
        "each value should count under its whole number rounded down (133.7 under 133);"
        " empty bins should be left out"
    )
    assert list(result["counts"]) == [101, 120, 133], "bins should be sorted, lowest first"
    assert all(
        isinstance(start, int) for start in result["counts"]
    ), "whole-number bin starts should be ints"


def test_grid_width_by_unit():
    result = grid([447.0, 440.0, 451.2, 1760.4], "hz")
    expected = {"unit": "hz", "width": 10, "counts": {440: 2, 450: 1, 1760: 1}}
    assert result == expected, "hz should count in 10 Hz bins: 447 under 440"
    result = grid([0.5, 0.9, 59.9, 60.0], "s")
    expected = {"unit": "s", "width": 1, "counts": {0: 2, 59: 1, 60: 1}}
    assert result == expected, "seconds should count in 1 s bins"
    result = grid([412, 380, 380], "words")
    expected = {"unit": "words", "width": 1, "counts": {380: 2, 412: 1}}
    assert result == expected, "a unit without its own width should count whole numbers"


def test_grid_empty():
    assert grid([], "bpm") is None, "no values should give no grid"
    missing = [None, float("nan"), float("inf")]
    assert grid(missing, "bpm") is None, "None, NaN and infinity should be left out"
