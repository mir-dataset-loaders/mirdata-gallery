"""Stats of single annotation types: beats, F0, multi-F0, notes, sections, lyrics and events."""

import numpy as np
from mirdata import annotations

from stats.annotation_types import F0, Beats, Events, Lyrics, MultiF0, Notes, Sections, bar_lengths, to_midi


def beats(positions):
    times = np.arange(len(positions)) * 0.5
    return annotations.BeatData(times, "s", np.array(positions), "bar_index")


def test_bar_lengths_split_where_the_count_goes_back_down():
    assert bar_lengths([1, 2, 3, 4, 1, 2, 3, 1, 2, 3, 4, 5, 6]) == [4, 3, 6]


def test_beats_outside_any_bar_are_ignored():
    assert bar_lengths([0, 0, 1, 2, 3, 1, 2, 3, 0]) == [3, 3]


def test_one_odd_bar_does_not_change_the_meter():
    """A 4/4 track with one 6-beat bar is in 4, as in RWC_P088."""
    stat = Beats()
    stat.add(beats([1, 2, 3, 4] * 3 + [1, 2, 3, 4, 5, 6] + [1, 2, 3, 4] * 3))
    assert stat.result()["meter"] == {4: 1}


def test_pickup_and_short_last_bar_do_not_change_the_meter():
    stat = Beats()
    stat.add(beats([3] + [1, 2, 3] * 4 + [1]))
    assert stat.result()["meter"] == {3: 1}


def test_meter_counts_tracks():
    stat = Beats()
    stat.add(beats([1, 2, 3, 4] * 2))
    stat.add(beats([1, 2, 3] * 2))
    stat.add(beats([1, 2, 3, 4] * 2))
    assert stat.result()["meter"] == {3: 1, 4: 2}


def f0(frequencies, voicing, voicing_unit="binary"):
    times = np.arange(len(frequencies)) * 0.01
    return annotations.F0Data(
        times, "s", np.array(frequencies, dtype=float), "hz", np.array(voicing, dtype=float), voicing_unit
    )


def test_f0_counts_every_voiced_frame():
    stat = F0()
    stat.add(f0([0, 220, 220, 220, 0], [0, 1, 1, 1, 0]))
    stat.add(f0([440, 440], [1, 1]))
    frequencies = stat.result()["frequencies"]
    assert frequencies["unit"] == "midi"
    assert sum(frequencies["counts"]) == 5  # 3 + 2 voiced frames; the silent ones are left out


def test_f0_unvoiced_frames_are_left_out_even_with_a_frequency():
    stat = F0()
    stat.add(f0([220, 300, 220], [1, 0, 1]))
    frequencies = stat.result()["frequencies"]
    assert sum(frequencies["counts"]) == 2
    assert frequencies["edges"] == [56.5, 57.5]  # A3 (220 Hz) only: 300 Hz was unvoiced


def test_f0_likelihood_voicing_is_voiced_from_one_half():
    stat = F0()
    stat.add(f0([220, 220, 220, 220], [0.1, 0.49, 0.5, 0.9], "likelihood"))
    assert sum(stat.result()["frequencies"]["counts"]) == 2


def test_f0_without_voiced_frames_has_no_histogram():
    stat = F0()
    stat.add(f0([0, 0], [0, 0]))
    assert stat.result() == {"frequencies": None}


def multif0(frequency_list):
    times = np.arange(len(frequency_list)) * 0.01
    return annotations.MultiF0Data(times, "s", frequency_list, "hz")


def test_multif0_counts_every_pitch_of_every_frame():
    stat = MultiF0()
    stat.add(multif0([[], [110.0, 220.0], [110.0, 220.0, 330.0]]))
    frequencies = stat.result()["frequencies"]
    assert frequencies["unit"] == "midi"
    assert sum(frequencies["counts"]) == 5


def test_multif0_polyphony_counts_frames_and_leaves_out_silence():
    stat = MultiF0()
    stat.add(multif0([[], [110.0], [110.0, 220.0], [110.0, 220.0], [0.0, 220.0]]))
    stat.add(multif0([[110.0, 220.0, 330.0], []]))
    assert stat.result()["polyphony"] == {1: 2, 2: 2, 3: 1}  # a 0 Hz pitch is no pitch


def test_multif0_without_pitches_has_no_histogram():
    stat = MultiF0()
    stat.add(multif0([[0.0], [0.0]]))
    assert stat.result() == {"frequencies": None, "polyphony": {}}


def notes(pitches, unit):
    intervals = np.array([[i, i + 1] for i in range(len(pitches))], dtype=float)
    return annotations.NoteData(intervals, "s", np.array(pitches, dtype=float), unit)


def test_pitches_are_counted_per_note_in_midi_whatever_unit_a_loader_gives():
    stat = Notes()
    stat.add(notes([440.0, 523.25], "hz"))  # A4, and C5 as 71.99996: as an Hz loader gives them
    stat.add(notes([69], "midi"))  # A4, as a MIDI loader gives it
    assert stat.result() == {"pitches": {"unit": "midi", "edges": [68.5, 69.5, 70.5, 71.5, 72.5], "counts": [2, 0, 0, 1]}}


def test_note_names_are_pitches_too():
    assert to_midi(["A4"], "note_name").tolist() == [69.0]


def test_no_pitch_and_pitch_classes_are_left_out():
    assert to_midi([0.0, -1.0, 440.0], "hz").tolist() == [69.0]  # 0 Hz: no pitch
    assert to_midi(["C", "G#"], "pc").tolist() == []  # no octave: no MIDI number


def test_notes_without_pitches_have_no_histogram():
    stat = Notes()
    stat.add(notes([0.0], "hz"))
    assert stat.result() == {"pitches": None}


def test_sections_count_labels_and_interval_lengths():
    stat = Sections()
    intervals = np.array([[0, 15], [15, 45], [45, 75], [75, 90]], dtype=float)
    stat.add(annotations.SectionData(intervals, "s", ["intro", "verse", "chorus", "verse"], "open"))
    result = stat.result()
    assert result["labels"] == {"verse": 2, "intro": 1, "chorus": 1}
    lengths = result["section_interval_seconds"]  # 15, 30, 30, 15 s
    assert lengths["unit"] == "s"
    assert sum(lengths["counts"]) == 4


def test_section_intervals_in_ms_are_converted_to_seconds():
    stat = Sections()
    stat.add(annotations.SectionData(np.array([[0, 15000], [15000, 45000]], dtype=float), "ms"))
    lengths = stat.result()["section_interval_seconds"]  # 15 and 30 s
    assert lengths["edges"][0] >= 10 and lengths["edges"][-1] <= 50


def lyrics(words, unit):
    intervals = np.array([[i, i + 0.5] for i in range(len(words))], dtype=float)
    return annotations.LyricData(intervals, "s", words, unit)


def test_lyrics_count_annotations_per_lyric_unit():
    stat = Lyrics()
    stat.add(lyrics(["hello", "world"], "words"))
    stat.add(lyrics(["hel", "lo"], "syllable_open"))
    stat.add(lyrics(["good", "bye"], "words"))
    assert stat.result()["lyric_unit"] == {"words": 2, "syllable_open": 1}


def test_lyrics_per_track_counts_the_lyrics_of_each_track():
    stat = Lyrics()
    stat.add(lyrics(["hello", "world"], "words"))
    stat.add(lyrics(["good", "bye", "my", "friend"], "words"))
    per_track = stat.result()["lyrics_per_track"]  # 2 and 4 words
    assert per_track["unit"] == "words"
    assert sum(per_track["counts"]) == 2
    assert per_track["edges"][0] <= 2 and per_track["edges"][-1] > 4


def test_lyrics_per_track_adds_up_every_annotation_of_a_track():
    stat = Lyrics()
    stat.add({"verse": lyrics(["a", "b", "c"], "words"), "chorus": lyrics(["d", "e"], "words")})
    per_track = stat.result()["lyrics_per_track"]  # one track with 5 words
    assert sum(per_track["counts"]) == 1
    assert per_track["edges"][0] <= 5 < per_track["edges"][-1]


def test_events_count_every_event():
    stat = Events()
    intervals = np.array([[0, 12], [12, 30], [30, 41]], dtype=float)
    stat.add(annotations.EventData(intervals, "s", ["vocals", "guitar", "vocals"], "open"))
    assert stat.result() == {"events": {"vocals": 2, "guitar": 1}}
