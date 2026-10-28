"""One Stat class per official mirdata annotation type.

A Stat reads one property's annotations track by track (add, read) and
turns them into grid counts and label counts at the end (result). A property
can hold several annotations at once (a dict, a MultiAnnotator or a list):
each one is read, and the track is counted once.
"""

from collections import Counter

import mirdata.annotations
import numpy as np

# The official mirdata annotation types (BeatData, ChordData, ... TempoData): the
# only ones the stats cover. Properties the card detection labels otherwise
# (Instrument, Genre) are ignored.
ANNOTATION_TYPES = {cls.__name__ for cls in mirdata.annotations.Annotation.__subclasses__()}
# grid() bin width per unit, the same for every dataset so the gallery can add
# datasets up bin by bin; any other unit (words, syllables, ...) counts whole numbers
GRID_WIDTHS = {"bpm": 1, "s": 1, "hz": 10, "midi": 1}


# ------------------------------------------------------------------ helpers


def to_seconds(values, unit):
    """Time values in seconds, or None when the unit is not a clock unit."""
    if unit == "s":
        return np.asarray(values, dtype=float)
    if unit == "ms":
        return np.asarray(values, dtype=float) / 1000.0
    return None


def interval_lengths(annotation):
    """Length in seconds of every interval of an interval-based annotation, or None."""
    intervals = np.asarray(annotation.intervals, dtype=float)
    unit = getattr(annotation, "interval_unit", "s")  # ChordData has no unit field
    if not len(intervals):
        return None
    return to_seconds(intervals[:, 1] - intervals[:, 0], unit)


def _number(x):
    """A Python int when x is integral, else a float with float noise removed."""
    x = round(float(x), 10)
    return int(x) if x == int(x) else x


def grid(values, unit):
    """{"unit", "width", "counts"} of the values, or None when there are none.

    counts maps the start of every bin that holds a value to how many it holds,
    lowest first; empty bins are left out. A value v goes in the bin starting
    at floor(v / width) * width, the width from GRID_WIDTHS: in bpm (width 1)
    133.7 counts under 133, in hz (width 10) 447 counts under 440.
    """
    width = GRID_WIDTHS.get(unit, 1)
    values = np.asarray([v for v in values if v is not None], dtype=float)
    values = values[np.isfinite(values)]
    if not len(values):
        return None
    starts, counts = np.unique(np.floor(values / width) * width, return_counts=True)
    return {
        "unit": unit,
        "width": width,
        "counts": {_number(s): int(c) for s, c in zip(starts, counts)},
    }


# ------------------------------------------------------------------- stats
# One Stat subclass per annotation type. read(value) takes one track's
# annotation object; result() turns everything read so far into the
# dataset-level distributions.


def unpack(value):
    """[(key, annotation)] for one track property's value.

    A dict gives its items, a MultiAnnotator its (annotator, annotation)
    pairs, a list or tuple its items with key None; anything else is a
    single annotation with key None.
    """
    if isinstance(value, dict):
        return [(str(k), v) for k, v in value.items()]
    if isinstance(value, mirdata.annotations.MultiAnnotator):
        annotators = value.annotators or [None] * len(value.annotations or [])
        return [
            (None if a is None else str(a), v)
            for a, v in zip(annotators, value.annotations or [])
        ]
    if isinstance(value, (list, tuple)):
        return [(None, v) for v in value]
    return [(None, value)]


def is_empty(value):
    """True for a property value that holds no annotation: None, a blank string, an empty container."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return True
    if isinstance(value, (dict, list, tuple, mirdata.annotations.MultiAnnotator)):
        return all(v is None for _, v in unpack(value))
    return False


class Stat:
    """Accumulates one annotation type over the tracks of a dataset."""

    annotation = mirdata.annotations.Annotation  # the mirdata class this Stat reads; set by each subclass

    def __init__(self):
        self.n_tracks = 0  # tracks whose annotation was read
        self.n_annotations = (
            0  # annotations read: more than n_tracks for dicts, multiple annotators
        )
        self.parts = Counter()  # dict keys / annotator ids the annotations came from

    def add(self, value):
        """Read one track's annotation(s); False when there is no mirdata annotation of this type."""
        found = [(k, v) for k, v in unpack(value) if isinstance(v, self.annotation)]
        if not found:
            return False
        for key, annotation in found:
            self.read(annotation)
            if key is not None:
                self.parts[key] += 1
        self.n_annotations += len(found)
        self.n_tracks += 1
        return True

    def summary(self):
        """The counts that head every entry: tracks, annotations, and parts when there are any."""
        head = {"n_tracks": self.n_tracks, "n_annotations": self.n_annotations}
        if self.parts:
            head["parts"] = dict(self.parts.most_common())
        return head

    def read(self, value):
        raise NotImplementedError

    def result(self):
        raise NotImplementedError


class Tempo(Stat):
    """BPM values of TempoData annotations."""

    annotation = mirdata.annotations.TempoData

    def __init__(self):
        super().__init__()
        self.bpm = []

    def read(self, value):
        self.bpm.extend(float(t) for t in value.tempos)

    def result(self):
        return {"tempo": grid(self.bpm, "bpm")}  # annotated by hand, unlike tempo_from_beats


class Beats(Stat):
    """Tempo from the beat intervals, and the meter as beats per bar (3/4 and 3/8 both count as 3)."""

    annotation = mirdata.annotations.BeatData

    def __init__(self):
        super().__init__()
        self.bpm = []  # one value per annotation, reported as tempo_from_beats
        self.meter = Counter()  # tracks per beats-per-bar count (3, 4, ...)

    def read(self, value):
        bpm = self.beat_bpm(value)
        if bpm is not None:
            self.bpm.append(bpm)
        meter = self.beat_meter(value)
        if meter is not None:
            self.meter[meter] += 1

    def result(self):
        return {
            "meter": dict(sorted(self.meter.items())),
            "tempo_from_beats": grid(self.bpm, "bpm"),  # 60 / median beat gap, not annotated
        }

    @staticmethod
    def beat_bpm(beats):
        """Tempo of one BeatData: 60 / its median beat gap; None without clock times or with fewer than 2 beats."""
        times = to_seconds(beats.times, beats.time_unit)
        if times is None or len(times) < 2:
            return None
        return 60.0 / float(np.median(np.diff(times)))

    @staticmethod
    def beat_meter(beats):
        """Beats per bar of one BeatData, or None without bar_index positions."""
        if beats.positions is None or beats.position_unit != "bar_index":
            return None
        lengths = Beats.bar_lengths(beats.positions)
        if not lengths:
            return None
        # the most common bar length: one odd bar does not change a track's meter
        return Counter(lengths).most_common(1)[0][0]

    @staticmethod
    def bar_lengths(positions):
        """Beats in every bar of bar_index positions: a bar ends where the count goes back down."""
        lengths, last = [], 0
        for p in np.asarray(positions, dtype=float):
            if p <= 0:  # 0 marks beats outside any bar
                continue
            if last and p <= last:
                lengths.append(int(last))
            last = p
        if last:
            lengths.append(int(last))
        return lengths


class Chords(Stat):
    """Chord labels and their qualities."""

    annotation = mirdata.annotations.ChordData

    def __init__(self):
        super().__init__()
        self.labels = Counter()
        self.qualities = Counter()

    def read(self, value):
        labels = [str(label) for label in value.labels]
        self.labels.update(labels)
        self.qualities.update(self.chord_quality(label) for label in labels)

    def result(self):
        return {
            "labels": dict(self.labels.most_common()),
            "qualities": dict(self.qualities.most_common()),
        }

    @staticmethod
    def chord_quality(label):
        """maj / min / 7 / N ... from a Harte-style chord label (a bare root is major)."""
        if label in ("N", "X"):
            return label
        if ":" not in label:
            return "maj"
        return label.split(":", 1)[1].split("/")[0].split("(")[0] or "maj"


class F0(Stat):
    """Frequencies of the voiced frames of frame-wise F0 annotations."""

    annotation = mirdata.annotations.F0Data

    def __init__(self):
        super().__init__()
        self.frequencies = []  # one array per annotation: its voiced frames, in Hz

    def read(self, value):
        self.frequencies.append(self.voiced_hz(value))

    def result(self):
        frequencies = np.concatenate(self.frequencies) if self.frequencies else []
        return {"frequencies": grid(frequencies, "hz")}

    @staticmethod
    def voiced_hz(f0):
        """The frequencies of one F0Data's voiced frames, in Hz."""
        frequencies = np.asarray(f0.frequencies, dtype=float)
        if f0.voicing is None:
            voiced = frequencies > 0
        elif f0.voicing_unit == "likelihood":  # a probability: voiced from 0.5 up
            voiced = np.asarray(f0.voicing, dtype=float) >= 0.5
        else:
            voiced = np.asarray(f0.voicing, dtype=float) > 0
        voiced &= frequencies > 0
        return mirdata.annotations.convert_pitch_units(frequencies[voiced], f0.frequency_unit, "hz")


class MultiF0(Stat):
    """Frequencies and polyphony (pitches sounding at once) of multi-pitch annotations."""

    annotation = mirdata.annotations.MultiF0Data

    def __init__(self):
        super().__init__()
        self.frequencies = []  # one array per annotation: every pitch of every frame, in Hz
        self.polyphony = Counter()  # frames per number of pitches; silent frames left out

    def read(self, value):
        frames = self.sounding_frames(value)
        self.polyphony.update(len(pitches) for pitches in frames)
        if frames:  # converted once per annotation, not frame by frame
            hz = mirdata.annotations.convert_pitch_units(np.concatenate(frames), value.frequency_unit, "hz")
            self.frequencies.append(hz)

    def result(self):
        frequencies = np.concatenate(self.frequencies) if self.frequencies else []
        return {
            "frequencies": grid(frequencies, "hz"),
            "polyphony": dict(sorted(self.polyphony.items())),
        }

    @staticmethod
    def sounding_frames(multif0):
        """The pitches of every frame of one MultiF0Data that has any, in its own unit; silent frames left out."""
        frames = []
        for frame in multif0.frequency_list:
            pitches = np.asarray(frame, dtype=float)
            pitches = pitches[pitches > 0]
            if len(pitches):
                frames.append(pitches)
        return frames


class Notes(Stat):
    """Pitch distribution of NoteData annotations, in the unit the loader gives.

    Hz is counted in 10 Hz bins, MIDI per note (rounded to the nearest one).
    """

    annotation = mirdata.annotations.NoteData

    def __init__(self):
        super().__init__()
        self.pitches = []  # one array per annotation, in self.unit
        self.unit = None  # the loader's pitch unit: every track of a property has the same

    def read(self, value):
        self.unit = value.pitch_unit
        pitches = np.asarray(value.pitches, dtype=float)
        self.pitches.append(pitches[pitches > 0])  # 0: no pitch

    def result(self):
        pitches = np.concatenate(self.pitches) if self.pitches else []
        if self.unit == "midi":
            pitches = np.rint(pitches)  # to the nearest note, as GuitarSet gives 43.98 for a 44
        return {"pitches": grid(pitches, self.unit)}


class Sections(Stat):
    """Section labels, and the length of every section interval in seconds."""

    annotation = mirdata.annotations.SectionData

    def __init__(self):
        super().__init__()
        self.section_interval_seconds = []
        self.labels = Counter()

    def read(self, value):
        if value.labels is not None:
            self.labels.update(str(label) for label in value.labels)
        lengths = interval_lengths(value)
        if lengths is not None:
            self.section_interval_seconds.extend(lengths.tolist())

    def result(self):
        return {
            "labels": dict(self.labels.most_common()),
            "section_interval_seconds": grid(self.section_interval_seconds, "s"),
        }


class Keys(Stat):
    """Key labels and modes of KeyData annotations."""

    annotation = mirdata.annotations.KeyData

    def __init__(self):
        super().__init__()
        self.keys = Counter()
        self.modes = Counter()

    def read(self, value):
        keys = [str(k) for k in value.keys]
        self.keys.update(keys)
        self.modes.update(self.key_mode(k) for k in keys)

    def result(self):
        return {"keys": dict(self.keys.most_common()), "modes": dict(self.modes.most_common())}

    @staticmethod
    def key_mode(key):
        """The mode of a key label: "minor" from "A:minor", "(none)" for a label without one."""
        return key.split(":", 1)[1] if ":" in key else "(none)"


class Lyrics(Stat):
    """How the lyrics are aligned (annotations per lyric_unit), and how many lyrics each track has."""

    annotation = mirdata.annotations.LyricData

    def __init__(self):
        super().__init__()
        self.lyric_unit = Counter()
        self.lyrics_per_track = []  # one value per track: its words, syllables, ... over all its annotations
        self.track_lyrics = 0

    def add(self, value):
        self.track_lyrics = 0
        if not super().add(value):
            return False
        self.lyrics_per_track.append(self.track_lyrics)
        return True

    def read(self, value):
        self.lyric_unit[value.lyric_unit] += 1
        self.track_lyrics += len(value.lyrics)

    def result(self):
        unit = max(self.lyric_unit, key=self.lyric_unit.get) if self.lyric_unit else None
        return {
            "lyric_unit": dict(self.lyric_unit.most_common()),
            "lyrics_per_track": grid(self.lyrics_per_track, unit),
        }


class Events(Stat):
    """Event labels: how often each one appears."""

    annotation = mirdata.annotations.EventData

    def __init__(self):
        super().__init__()
        self.events = Counter()

    def read(self, value):
        self.events.update(str(e) for e in value.events)

    def result(self):
        return {"events": dict(self.events.most_common())}


STATS = {
    "TempoData": Tempo,
    "BeatData": Beats,
    "ChordData": Chords,
    "F0Data": F0,
    "MultiF0Data": MultiF0,
    "NoteData": Notes,
    "SectionData": Sections,
    "KeyData": Keys,
    "LyricData": Lyrics,
    "EventData": Events,
}
assert all(stat.annotation.__name__ == name for name, stat in STATS.items())
assert set(STATS) == ANNOTATION_TYPES, "one Stat per official annotation type"
