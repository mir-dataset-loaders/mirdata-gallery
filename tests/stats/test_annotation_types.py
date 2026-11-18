"""The Stat classes of stats/annotation_types.py, fed mirdata annotations built in code.

Numeric fields are compared with grid() of the values a Stat should collect;
the exact bins are checked by hand only in test_grid*.
"""

import mirdata.datasets.baf
import numpy as np
import pytest
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
    choose_stat,
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


def beats_from_gaps(*gaps):
    """Beats from 0 s on, the given gaps apart."""
    return beats(np.concatenate([[0.0], np.cumsum(gaps)]))


def bars(*lengths):
    """Beats in bars of the given lengths: bar_index positions 1, 2, ... in each."""
    positions = [p for n in lengths for p in range(1, n + 1)]
    return beats(range(len(positions)), positions)


def events(*labels):
    return annotations.EventData(
        intervals(*[(i, i + 1) for i in range(len(labels))]), "s", list(labels), "open"
    )


def events_extended(*labels):
    """baf's EventDataExtended: events with a tag each."""
    return mirdata.datasets.baf.EventDataExtended(
        intervals(*[(i, i + 1) for i in range(len(labels))]),
        "s",
        list(labels),
        "open",
        ["tag"] * len(labels),
        "open",
    )


def collect(stat, *values):
    """The Stat after reading one value per track."""
    for value in values:
        stat.add(value)
    return stat


# ---------------------------------------------------------------- one Stat each


def tempos(values, confidence=None):
    """A TempoData whose values all span the same 0-10 s, like giantsteps_tempo's candidates."""
    return annotations.TempoData(
        intervals(*[(0, 10)] * len(values)),
        "s",
        np.array(values, dtype=float),
        "bpm",
        None if confidence is None else np.array(confidence, dtype=float),
        None if confidence is None else "likelihood",
    )


def test_tempo():
    track1 = tempos([120.0], [1.0])
    track2 = tempos([87.0, 174.0], [0.22, 0.78])
    result = collect(Tempo(), track1, track2).result()
    expected = {"tempo": grid([120.0, 174.0], "bpm")}
    assert (
        result == expected
    ), "each annotation should give one tempo, its most confident, on one 1-bpm grid"


def test_tempo_first_value():
    tie = tempos([127.0, 139.0], [0.5, 0.5])
    no_confidence = tempos([90.0, 180.0])
    result = collect(Tempo(), tie, no_confidence).result()
    expected = {"tempo": grid([127.0, 90.0], "bpm")}
    assert (
        result == expected
    ), "the first tempo should be taken on a confidence tie, or without confidences"


def test_tempo_plain_values():
    carnatic = {
        "tempo_apm": 425,
        "tempo_bpm": 106,
        "sama_interval": 4.522,
        "beats_per_cycle": 32,
        "subdivisions": 4,
    }
    stat = collect(Tempo(), 120.5, 90, "125.0", carnatic)
    expected = {"tempo": grid([120.5, 90.0, 125.0, 106.0], "bpm")}
    assert (
        stat.result() == expected
    ), "a number, a numeric string and saraga_carnatic's tempo_bpm should each be one tempo"
    assert (stat.n_tracks, stat.n_annotations) == (
        4,
        4,
    ), "each plain tempo should count as one track with one annotation"


def test_tempo_not_read():
    # saraga_hindustani: per-section tempos in matras per minute, -1 when unmetered
    hindustani = {"Alap": {"tempo": -1, "start_time": 0.0, "duration": 38.1}}
    stat = Tempo()
    assert not stat.add(hindustani), "a dict without tempo_bpm should not be read"
    assert not stat.add("fast"), "a string that isn't a number should not be read"
    assert stat.n_tracks == 0, "a value that isn't read should not count as a track"


def test_beats():
    every_half_second = [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5]
    bars_of_4 = [1, 2, 3, 4, 1, 2, 3, 4, 1, 2]  # two bars of 4, then 2 beats
    in_ms = beats([0, 1000, 2000, 3000, 4000, 5000], [1, 2, 3, 1, 2, 3], time_unit="ms")
    speeding_up = beats_from_gaps(*[0.6] * 5, *[0.45] * 5)  # 100 bpm, then 133.3 bpm
    one_change = beats(
        range(15), [1, 2, 3, 4, 1, 2, 3, 1, 2, 3, 4, 1, 2, 3, 4], time_unit="ticks"
    )  # bars of 4 3 4 4, no tempo
    result = collect(
        Beats(),
        beats(every_half_second, bars_of_4),  # 120 bpm, meter 4
        in_ms,  # 60 bpm, meter 3
        beats([0, 0.25, 0.5], [1, 2, 3], position_unit="global_index"),  # 240 bpm
        beats([0.0]),  # one beat
        beats([0, 1, 2], time_unit="ticks"),
        speeding_up,  # median gap 0.525 s, no positions
        one_change,
    ).result()
    tempo = grid([120.0, 60.0, 240.0, 60 / 0.525], "bpm")
    assert result["tempo_from_beats"] == tempo, (
        "tempo should be 60 / the median beat gap, one per annotation, with ms read as s/1000;"
        " one beat or a non-clock unit (ticks) should give no tempo"
    )
    assert result["meter"] == {3: 1, 4: 2}, (
        "meter should be each track's most common bar length (a short last bar does not"
        " change it); positions that are not bar_index should give no meter"
    )
    tempo_changes = {"tempo": [120, 60, 240, 114.3], "change": [0, 0, 0, 33.3]}
    assert result["tempo_changes"] == tempo_changes, (
        "tempo_changes should list the tempo and the change in % of each annotation that"
        " has a tempo, the i-th of each together, in the order read, rounded to 0.1"
    )
    assert result["meter_changes"] == {0: 2, 1: 1}, (
        "meter_changes should count the tracks by how many times each leaves its"
        " meter"
    )


def test_beats_empty():
    one_beat, ticks = beats([0.0]), beats([0, 1, 2], time_unit="ticks")
    result = collect(Beats(), one_beat, ticks).result()
    assert (
        result["tempo_from_beats"] is None
    ), "with no annotation that has a tempo, tempo_from_beats should be null"
    assert (
        result["tempo_changes"] is None
    ), "with no annotation that has a tempo, tempo_changes should be null"
    assert result["meter"] == {}, "with no bar_index positions, meter should be empty"
    assert (
        result["meter_changes"] == {}
    ), "with no bar_index positions, meter_changes should be empty, like meter"


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

    in_hz = annotations.NoteData(
        two_notes, "s", np.array([440.0, 0.0]), "hz"
    )  # 0: no pitch
    higher = annotations.NoteData(two_notes, "s", np.array([880.0, 1760.0]), "hz")
    result = collect(Notes(), in_hz, higher).result()
    expected = {"pitches": grid([440.0, 880.0, 1760.0], "hz")}
    assert (
        result == expected
    ), "Hz pitches should be counted in Hz, without the 0s (no pitch)"


def test_sections():
    track1 = annotations.SectionData(
        intervals((0, 10), (10, 30)), "s", ["verse", "chorus"], "open"
    )
    track2 = annotations.SectionData(intervals((0, 5000)), "ms", ["verse"], "open")
    track3 = annotations.SectionData(intervals((0, 40)), "s")  # no labels
    result = collect(Sections(), track1, track2, track3).result()
    assert set(result) == {"sections_per_annotation", "section_interval_seconds"}, (
        "sections should give only the sections per annotation and the section"
        " lengths; labels are not counted"
    )
    assert result["sections_per_annotation"] == grid([2, 1, 1], "sections"), (
        "every annotation should add its number of sections, labeled or not,"
        " on a grid of whole numbers"
    )
    lengths = grid([10.0, 20.0, 5.0, 40.0], "s")
    assert result["section_interval_seconds"] == lengths, (
        "every section's length in seconds (ms read as s/1000), labeled or not,"
        " should be counted on one 1 s grid"
    )


def test_sections_per_annotation_counts_each_annotator():
    three = annotations.SectionData(intervals((0, 10), (10, 20), (20, 30)), "s")
    one = annotations.SectionData(intervals((0, 30)), "s")
    two_annotators = annotations.MultiAnnotator(
        ["ann1", "ann2"], [three, one], annotations.SectionData
    )
    result = collect(Sections(), two_annotators).result()
    assert result["sections_per_annotation"] == grid([3, 1], "sections"), (
        "a track with two annotators should add one value per annotation"
        " (3 and 1), not one summed value for the track (4)"
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


def test_keys_plain_strings():
    # giantsteps_key, beatport_key (a list), multivox: one key per track, as text
    stat = collect(
        Keys(), "C minor", "E major | E minor", ["E minor ", " E major"], "Fm", "X"
    )
    keys = {"E:minor": 2, "E:major": 2, "C:minor": 1, "Fm": 1, "X": 1}
    assert (
        stat.result()["keys"] == keys
    ), "every key in a string, a list or split on | should count, as a root:mode label"
    modes = {"minor": 3, "major": 2, "(none)": 2}
    assert (
        stat.result()["modes"] == modes
    ), "a key string's mode should count; one without a mode is (none)"
    assert (stat.n_tracks, stat.n_annotations) == (
        5,
        5,
    ), "each plain value should count as one track with one annotation"


def test_keys_mode_from_track():
    class Track:  # fma_keys: the key and its mode are two names of the track
        mode = "Major"

    stat = Keys()
    stat.add("F#", Track())
    stat.add("C minor", Track())
    keys = {"F#:major": 1, "C:minor": 1}
    assert (
        stat.result()["keys"] == keys
    ), "a key without a mode should take the track's mode; one with a mode keeps it"


def test_keys_not_read():
    stat = Keys()
    da_tacos = {"key": b"C", "scale": b"major", "strength": 0.8}
    assert not stat.add(da_tacos), "a dict (da_tacos' essentia estimate) should not be read"
    assert not stat.add(6), "a number (fma_keys' key_number) should not be read"
    music21 = [{"time": 0, "key": object()}]
    assert not stat.add(music21), "a list of non-strings (haydn_op20) should not be read"
    assert stat.n_tracks == 0, "a value that isn't read should not count as a track"


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
    assert (
        len(result["events"]) == 41
    ), "every label should be kept, however many there are"
    assert "(other)" not in result["events"], "no labels should be folded into (other)"
    assert list(result["events"])[0] == "kick", "labels should come most common first"


def test_events_extended():
    result = collect(Events(), events_extended("kick", "snare")).result()
    expected = {"events": {"kick": 1, "snare": 1}}
    assert result == expected, "Events should count baf's EventDataExtended labels"


# ---------------------------------------------------------------- choose_stat


def test_choose_stat_by_value():
    sections = annotations.SectionData(intervals((0, 10)), "s", ["verse"], "open")
    f0 = annotations.F0Data(
        np.array([0.0, 0.01]),
        "s",
        np.array([440.0, 440.0]),
        "hz",
        np.array([1.0, 1.0]),
        "binary",
    )
    chords = annotations.ChordData(intervals((0, 1)), "s", ["C:maj"], "harte")
    two_annotators = annotations.MultiAnnotator(
        ["ann1", "ann2"], [sections, sections], annotations.SectionData
    )
    chosen = {
        "beats": choose_stat("beats", beats([1.0, 2.0])),
        "leadsheet_chords": choose_stat("leadsheet_chords", chords),
        "pitch_contours": choose_stat("pitch_contours", {"E": f0, "A": f0}),
        "sections_uppercase": choose_stat("sections_uppercase", two_annotators),
        "tempo_v2": choose_stat("tempo_v2", tempos([120.0])),
        "matches": choose_stat("matches", events_extended("kick")),
    }
    expected = {
        "beats": "BeatData",
        "leadsheet_chords": "ChordData",
        "pitch_contours": "F0Data",
        "sections_uppercase": "SectionData",
        "tempo_v2": "TempoData",
        "matches": "EventDataExtended",
    }
    assert chosen == expected, (
        "an annotation, or one inside a dict or MultiAnnotator, should give the"
        " name of its class, whatever the name of the property"
    )


def test_choose_stat_by_name():
    for value in (120.0, 96, "125.0", {"tempo_bpm": 80}):
        assert (
            choose_stat("tempo", value) == "TempoData"
        ), f"a plain value under a tempo name should be TempoData ({value!r})"
    assert (
        choose_stat("tempo_beats", beats([1.0, 2.0])) == "BeatData"
    ), "the value should come first: an annotation under a tempo name keeps its own type"
    key_names = {
        "key": "C minor",  # giantsteps_key
        "keys_music21": [{"time": 0, "key": object()}],  # haydn_op20
        "key_number": 6,  # fma_keys
    }
    for name, value in key_names.items():
        assert (
            choose_stat(name, value) == "KeyData"
        ), f"a plain value under a key or keys name should be KeyData ({name})"


def test_choose_stat_none():
    class MyBeats(annotations.BeatData):
        pass

    not_read = {
        "title": "Anna (Go To Him)",
        "duration": 120.0,
        "tempos": 120.0,
        "keyboard": "Steinway",
        "mode": "Major",
        "vggish": (np.zeros(2), np.zeros(2)),
        "my_beats": MyBeats(np.array([1.0]), "s", None, None),
    }
    for name, value in not_read.items():
        assert choose_stat(name, value) is None, (
            f"{name} should not be read: no class name in STATS, and no"
            " tempo, key or keys word in the name"
        )


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
        assert (
            Chords.chord_quality(label) == quality
        ), f"{label} should have quality {quality}"


def test_key_label():
    class Track:
        mode = "Major"

    expected = [
        ("C minor", None, "C:minor"),
        ("Eb minor dorian", None, "Eb:minor dorian"),
        (" E major", None, "E:major"),
        ("A Minor", None, "A:minor"),
        ("C:minor", None, "C:minor"),
        ("Fm", None, "Fm"),
        ("X", None, "X"),
        ("F#", Track(), "F#:major"),
        ("C minor", Track(), "C:minor"),
    ]
    for key, track, label in expected:
        assert (
            Keys.key_label(key, track) == label
        ), f"{key!r} (track mode {getattr(track, 'mode', None)!r}) should be {label!r}"


def test_bar_lengths():
    bars = Beats.bar_lengths([1, 2, 3, 4, 1, 2, 3])
    assert bars == [4, 3], "a bar should end where the count goes back down"
    bars = Beats.bar_lengths([0, 0, 1, 2, 1, 2])
    assert bars == [2, 2], "position 0 (a beat outside any bar) should be skipped"
    assert Beats.bar_lengths([]) == [], "no positions should give no bars"


def test_beat_meter():
    meter = Beats.beat_meter(bars(4, 4, 3, 4, 4))
    assert meter == (4, 1), (
        "the meter should be the most common bar length, and one bar of another length"
        " one change"
    )
    meter = Beats.beat_meter(bars(4, 4, 3, 3, 4, 4))
    assert meter == (4, 1), "a run of the same odd length should count once"
    meter = Beats.beat_meter(bars(4, 4, 3, 3, 2, 4, 4))
    assert meter == (4, 2), (
        "switching to another odd length should count again; going back to the meter"
        " should not"
    )
    meter = Beats.beat_meter(bars(4, 3, 4, 4, 5, 4))
    assert meter == (4, 2), "every time the bars leave the meter should count"
    meter = Beats.beat_meter(bars(2, 4, 4, 4, 1))
    assert meter == (4, 0), (
        "a first or last bar shorter than the meter may be cut short (a pickup, the last"
        " downbeat) and should not count"
    )
    meter = Beats.beat_meter(bars(8, 4, 4, 4))
    assert meter == (4, 1), (
        "a first bar longer than the meter should count: a pickup or a cut-short bar"
        " is always shorter"
    )
    meter = Beats.beat_meter(beats([0, 1, 2], [1, 2, 3], position_unit="global_index"))
    assert meter == (None, None), (
        "positions that are not bar_index, like global_index, should give no meter"
        " and no changes"
    )


def test_beat_tempo():
    _, change = Beats.beat_tempo(beats_from_gaps(*[0.5] * 10, *[0.4] * 10))
    assert change == pytest.approx(25.0), (
        "change should be the end tempo over the start tempo, minus 1, in %: the start"
        " from the gaps in the first 10% of the track, the end from the last 10%"
    )
    _, change = Beats.beat_tempo(beats_from_gaps(*[0.4] * 10, *[0.5] * 10))
    assert change == pytest.approx(-20.0), "slowing down should give a negative change"
    _, change = Beats.beat_tempo(beats_from_gaps(0.5, 0.7, 0.5, *[0.5] * 27))
    assert change == pytest.approx(
        0.0
    ), "one odd gap should not move the start or end: each is 60 / the median gap"
    _, change = Beats.beat_tempo(beats_from_gaps(*[0.5] * 10, *[0.4] * 10, *[0.5] * 10))
    assert change == pytest.approx(
        0.0
    ), "a tempo change between the first and last 10% should not count"
    _, change = Beats.beat_tempo(beats_from_gaps(0.5, 0.4))
    assert change == pytest.approx(
        25.0
    ), "each edge should hold at least its first / last gap, however short the track"
    assert Beats.beat_tempo(beats([0, 0.5]))[1] == pytest.approx(
        0.0
    ), "2 beats should be enough for a change"
    assert Beats.beat_tempo(beats([0.0])) == (
        None,
        None,
    ), "one beat should give no tempo and no change"
    assert Beats.beat_tempo(beats([0, 1, 2], time_unit="ticks")) == (
        None,
        None,
    ), "times not in a clock unit should give no tempo and no change"


def test_grid():
    result = grid([133.7, 101.9, 133.2, 120.0, 133.0], "bpm")
    expected = {"unit": "bpm", "width": 1, "counts": {101: 1, 120: 1, 133: 3}}
    assert result == expected, (
        "each value should count under its whole number rounded down (133.7 under 133);"
        " empty bins should be left out"
    )
    assert list(result["counts"]) == [
        101,
        120,
        133,
    ], "bins should be sorted, lowest first"
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
