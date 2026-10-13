"""A tiny mirdata loader for the tests, written like a real one (see mirdata's beatles.py).

Its files are in tests/resources/mir_datasets/fake_dataset/, its index in
tests/resources/fake_dataset_index_1.0.json. The numbers are small enough to
check by hand:

    track    audio                 beats (time, position)          chords
    track1   2 s, 8000 Hz          every 0.5 s, 1 2 3 4  (120 bpm)  C:maj, A:min       (1 s each)
    track2   4 s, 8000 Hz          every 1 s,   1 2 3 1  (60 bpm)   C:maj, G:7, N      (2 s, 1 s, 1 s)
    track3   1 s, 16000 Hz         every 0.25 s, 1 2 3 4 (240 bpm)  none (null in the index)

conftest.py adds it to mirdata's list of datasets, so mirdata.initialize("fake_dataset")
works like for any other dataset.
"""

import csv
import os
from typing import BinaryIO, Optional, TextIO, Tuple

import librosa
import numpy as np
from mirdata import annotations, core, io

NAME = "fake_dataset"
RESOURCES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources")
DATA_HOME = os.path.join(RESOURCES, "mir_datasets", NAME)

BIBTEX = """@misc{fake_dataset, title={A fake dataset for the mirdata-gallery tests}}"""

INDEXES = {
    "default": "1.0",
    "test": "1.0",
    "1.0": core.Index(filename="fake_dataset_index_1.0.json"),
}
# mirdata looks for an index without a url in its own tests folder: point it to ours.
INDEXES["1.0"].indexes_dir = RESOURCES

REMOTES = None

LICENSE_INFO = "Creative Commons Attribution 4.0 International"


class Track(core.Track):
    """fake_dataset track class

    Cached Properties:
        beats (BeatData): beat annotations
        chords (ChordData): chord annotations
    """

    def __init__(self, track_id, data_home, dataset_name, index, metadata):
        super().__init__(track_id, data_home, dataset_name, index, metadata)
        self.audio_path = self.get_path("audio")
        self.beats_path = self.get_path("beats")
        self.chords_path = self.get_path("chords")

    @core.cached_property
    def beats(self) -> Optional[annotations.BeatData]:
        return load_beats(self.beats_path)

    @core.cached_property
    def chords(self) -> Optional[annotations.ChordData]:
        return load_chords(self.chords_path)

    @property
    def audio(self) -> Optional[Tuple[np.ndarray, float]]:
        return load_audio(self.audio_path)


@io.coerce_to_bytes_io
def load_audio(fhandle: BinaryIO) -> Tuple[np.ndarray, float]:
    return librosa.load(fhandle, sr=None, mono=True)


@io.coerce_to_string_io
def load_beats(fhandle: TextIO) -> annotations.BeatData:
    """One beat per line: time in seconds, tab, position in the bar."""
    times, positions = [], []
    for line in csv.reader(fhandle, delimiter="\t"):
        times.append(float(line[0]))
        positions.append(int(line[1]))
    return annotations.BeatData(np.array(times), "s", np.array(positions), "bar_index")


@io.coerce_to_string_io
def load_chords(fhandle: TextIO) -> annotations.ChordData:
    """One chord per line: start, end (seconds) and a Harte label, tab-separated."""
    intervals, labels = [], []
    for line in csv.reader(fhandle, delimiter="\t"):
        intervals.append([float(line[0]), float(line[1])])
        labels.append(line[2])
    return annotations.ChordData(np.array(intervals), "s", labels, "harte")


class Dataset(core.Dataset):
    """The fake_dataset dataset"""

    def __init__(self, data_home=None, version="default"):
        super().__init__(
            data_home,
            version,
            name=NAME,
            track_class=Track,
            bibtex=BIBTEX,
            indexes=INDEXES,
            remotes=REMOTES,
            license_info=LICENSE_INFO,
        )
