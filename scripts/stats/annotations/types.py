"""One Stat class per official mirdata annotation type.

A Stat reads one property's annotations track by track (add, read) and
turns them into histograms and label counts at the end (result). A property
can hold several annotations at once (a dict, a MultiAnnotator or a list):
each one is read, and the track is counted once.
"""

from collections import Counter

import numpy as np
from mirdata import annotations
from mirdata.annotations import Annotation, MultiAnnotator

from stats.histograms import histogram

TOP = 10  # how many labels to keep per label distribution
# The official mirdata annotation types (BeatData, ChordData, ... TempoData): the
# only ones the stats cover. Properties the card detection labels otherwise
# (Instrument, Genre) are ignored.
ANNOTATION_TYPES = {cls.__name__ for cls in Annotation.__subclasses__()}


# ------------------------------------------------------------------ helpers


def top_counts(counter, top=TOP):
    """The most common labels, with the rest folded into "(other)"."""
    result = dict(counter.most_common(top))
    rest = sum(counter.values()) - sum(result.values())
    if rest:
        result["(other)"] = rest
    return result


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


def chord_quality(label):
    """maj / min / 7 / N ... from a Harte-style chord label (a bare root is major)."""
    if label in ("N", "X"):
        return label
    if ":" not in label:
        return "maj"
    return label.split(":", 1)[1].split("/")[0].split("(")[0] or "maj"


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
    if isinstance(value, MultiAnnotator):
        annotators = value.annotators or [None] * len(value.annotations or [])
        return [
            (None if a is None else str(a), v) for a, v in zip(annotators, value.annotations or [])
        ]
    if isinstance(value, (list, tuple)):
        return [(None, v) for v in value]
    return [(None, value)]


def is_empty(value):
    """True for a property value that holds no annotation: None, a blank string, an empty container."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return True
    if isinstance(value, (dict, list, tuple, MultiAnnotator)):
        return all(v is None for _, v in unpack(value))
    return False


class Stat:
    """Accumulates one annotation type over the tracks of a dataset."""

    annotation = Annotation  # the mirdata class this Stat reads; set by each subclass

    def __init__(self):
        self.n_tracks = 0  # tracks whose annotation was read
        self.n_annotations = 0  # annotations read: more than n_tracks for dicts, multiple annotators
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
            head["parts"] = top_counts(self.parts)
        return head

    def read(self, value):
        raise NotImplementedError

    def result(self):
        raise NotImplementedError


class Tempo(Stat):
    """BPM values of TempoData annotations."""

    annotation = annotations.TempoData

    def __init__(self):
        super().__init__()
        self.bpm = []

    def read(self, value):
        self.bpm.extend(float(t) for t in value.tempos)

    def result(self):
        return {"tempo": histogram(self.bpm, "bpm")}  # same name as the tempo derived from beats


class Beats(Stat):
    """Tempo from the beat intervals, and beats per bar (meter)."""

    annotation = annotations.BeatData

    def __init__(self):
        super().__init__()
        self.bpm = []  # one value per annotation, reported as the dataset's tempo
        self.beats_per_bar = Counter()  # tracks per meter

    def read(self, value):
        times = to_seconds(value.times, value.time_unit)
        if times is not None and len(times) > 1:
            self.bpm.append(60.0 / float(np.median(np.diff(times))))
        if value.positions is not None and value.position_unit == "bar_index":
            positions = np.asarray(value.positions, dtype=float)
            positions = positions[positions > 0]  # 0 marks beats outside any bar
            if len(positions):
                self.beats_per_bar[int(positions.max())] += 1

    def result(self):
        return {
            "beats_per_bar": dict(sorted(self.beats_per_bar.items())),
            "tempo": histogram(self.bpm, "bpm"),  # tempo derived from the beats
        }


class Chords(Stat):
    """Chord labels and their qualities."""

    annotation = annotations.ChordData

    def __init__(self):
        super().__init__()
        self.labels = Counter()
        self.qualities = Counter()

    def read(self, value):
        labels = [str(label) for label in value.labels]
        self.labels.update(labels)
        self.qualities.update(chord_quality(label) for label in labels)

    def result(self):
        return {
            "labels": top_counts(self.labels),
            "qualities": top_counts(self.qualities),
        }


class F0(Stat):
    """Pitch and voiced fraction of frame-wise F0 annotations."""

    annotation = annotations.F0Data

    def __init__(self):
        super().__init__()
        self.voiced_fraction = []
        self.f0_median = []  # one value per annotation, over its voiced frames
        self.units = Counter()

    def read(self, value):
        frequencies = np.asarray(value.frequencies, dtype=float)
        if value.voicing is not None:
            voicing = np.asarray(value.voicing, dtype=float)
        else:
            voicing = frequencies > 0
        voiced = frequencies[(voicing > 0) & (frequencies > 0)]
        self.voiced_fraction.append(len(voiced) / len(frequencies) if len(frequencies) else 0.0)
        if len(voiced):
            self.f0_median.append(float(np.median(voiced)))
        self.units[value.frequency_unit] += 1

    def result(self):
        unit = max(self.units, key=self.units.get) if self.units else None
        return {
            "voiced_fraction": histogram(self.voiced_fraction, "fraction"),
            "f0_median_per_annotation": histogram(self.f0_median, unit),
        }


class MultiF0(Stat):
    """Polyphony of multi-pitch annotations."""

    annotation = annotations.MultiF0Data

    def __init__(self):
        super().__init__()
        self.max_polyphony = []

    def read(self, value):
        counts = [len(f) for f in value.frequency_list]
        self.max_polyphony.append(max(counts) if counts else 0)

    def result(self):
        return {"max_polyphony": histogram(self.max_polyphony, "voices")}


class Notes(Stat):
    """Pitch distribution of NoteData annotations."""

    annotation = annotations.NoteData

    def __init__(self):
        super().__init__()
        self.pitches = []
        self.units = Counter()

    def read(self, value):
        self.pitches.extend(np.asarray(value.pitches, dtype=float).tolist())
        self.units[value.pitch_unit] += 1

    def result(self):
        unit = max(self.units, key=self.units.get) if self.units else None
        return {"pitch": histogram(self.pitches, unit)}


class Sections(Stat):
    """Section labels and section lengths."""

    annotation = annotations.SectionData

    def __init__(self):
        super().__init__()
        self.section_seconds = []
        self.labels = Counter()

    def read(self, value):
        if value.labels is not None:
            self.labels.update(str(label) for label in value.labels)
        lengths = interval_lengths(value)
        if lengths is not None:
            self.section_seconds.extend(lengths.tolist())

    def result(self):
        return {
            "labels": top_counts(self.labels),
            "section_seconds": histogram(self.section_seconds, "s", log=True),
        }


class Keys(Stat):
    """Key labels and modes of KeyData annotations."""

    annotation = annotations.KeyData

    def __init__(self):
        super().__init__()
        self.keys = Counter()
        self.modes = Counter()

    def read(self, value):
        keys = [str(k) for k in value.keys]
        self.keys.update(keys)
        self.modes.update(k.split(":", 1)[1] if ":" in k else "(none)" for k in keys)

    def result(self):
        return {"keys": top_counts(self.keys), "modes": top_counts(self.modes)}


class Lyrics(Stat):
    """Lyrics: only the counts every type has (tracks, annotations)."""

    annotation = annotations.LyricData

    def read(self, value):
        pass

    def result(self):
        return {}


class Events(Stat):
    """Event labels."""

    annotation = annotations.EventData

    def __init__(self):
        super().__init__()
        self.labels = Counter()

    def read(self, value):
        self.labels.update(str(e) for e in value.events)

    def result(self):
        return {"labels": top_counts(self.labels)}


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
