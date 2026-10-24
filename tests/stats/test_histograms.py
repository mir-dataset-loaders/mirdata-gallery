"""Histogram bins: one rule for the width (Freedman-Diaconis, at most MAX_BINS bins), tidy edges."""

import math

import numpy as np
import pytest

from stats.histograms import MAX_BINS, histogram, note_histogram, tidy_width


def width(hist):
    return hist["edges"][1] - hist["edges"][0]


def is_tidy(w):
    """1, 2 or 5 times a power of ten."""
    scaled = w / 10 ** math.floor(math.log10(w))
    return any(math.isclose(scaled, step) for step in (1, 2, 5, 10))  # 10: 0.00999... read off rounded edges


@pytest.mark.parametrize(
    "raw, closest, up",
    [(1.4, 1, 2), (37, 50, 50), (0.3, 0.2, 0.5), (2.6, 2, 5), (5, 5, 5), (7.5, 10, 10)],
)
def test_tidy_width(raw, closest, up):
    assert math.isclose(tidy_width(raw), closest)
    assert math.isclose(tidy_width(raw, up=True), up)


@pytest.mark.parametrize("seed", range(20))
def test_never_more_than_max_bins_and_always_tidy(seed):
    rng = np.random.default_rng(seed)
    scale = 10 ** rng.uniform(-2, 4)
    values = rng.normal(0, scale, int(rng.integers(5, 5000))) + rng.uniform(-scale, scale) * 10
    hist = histogram(values, "x")
    assert len(hist["counts"]) <= MAX_BINS
    assert is_tidy(width(hist))
    assert sum(hist["counts"]) == len(values)


def test_whole_number_data_gets_whole_number_bins():
    """Whole numbers from 38 to 90 (lyrics per track, say): every bin holds the same number of them."""
    hist = histogram(np.repeat(np.arange(38, 91), 100), "words")
    assert width(hist) == 5
    assert all(isinstance(e, int) for e in hist["edges"])
    assert hist["counts"][1:-1] == [500] * (len(hist["counts"]) - 2)  # no 2-3-2-3 zigzag


def test_the_narrowest_width_that_fits_max_bins_is_used():
    """100.5 to 2599 fits MAX_BINS (25) bins of 100 exactly."""
    values = np.linspace(100.5, 2599, 100000)
    hist = histogram(values, "x")
    assert width(hist) == 100
    assert len(hist["counts"]) == MAX_BINS


def test_aligned_edges_that_need_one_more_bin_take_the_next_width():
    """0 to 125 with width 5 needs 26 bins (125 opens its own bin): width 10, 13 bins."""
    hist = histogram(np.linspace(0, 125, 100000), "x")
    assert width(hist) == 10
    assert len(hist["counts"]) == 13


def test_freedman_diaconis_gives_wider_bins_to_small_datasets():
    rng = np.random.default_rng(0)
    few = histogram(np.append(rng.uniform(0, 100, 18), [0, 100]), "x")  # same range, 20 values
    many = histogram(np.append(rng.uniform(0, 100, 4998), [0, 100]), "x")  # and 5000 values
    assert width(few) > width(many)
    assert len(few["counts"]) < MAX_BINS


def test_mostly_equal_values_still_get_bins():
    """The middle 50% has no spread (Freedman-Diaconis width 0): the bin limit decides."""
    hist = histogram([5] * 10 + [7, 50], "x")
    assert len(hist["counts"]) <= MAX_BINS
    assert sum(hist["counts"]) == 12


def test_one_repeated_value_gets_one_bin():
    hist = histogram([120, 120, 120], "bpm")
    assert len(hist["counts"]) == 1
    assert hist["edges"][0] <= 120 < hist["edges"][1]


def test_missing_and_infinite_values_are_left_out():
    hist = histogram([1, None, 2, float("nan"), float("inf"), 3], "x")
    assert sum(hist["counts"]) == 3
    assert histogram([None, float("nan")], "x") is None


def test_log_edges_are_1_2_5_times_powers_of_ten():
    hist = histogram([1.5, 30, 150, 0, -1], "s", log=True)
    assert hist["edges"] == [1, 2, 5, 10, 20, 50, 100, 200]
    assert sum(hist["counts"]) == 3  # 0 and -1 cannot go on a log scale


def test_pitches_get_one_bin_per_note_centred_on_it():
    hist = note_histogram([60, 60.3, 59.7, 62, 71.99996])  # 59.7 and 60.3 are C4 too; 71.99996 is C5 (523.25 Hz)
    assert hist["unit"] == "midi"
    assert hist["edges"][:3] == [59.5, 60.5, 61.5] and hist["edges"][-1] == 72.5
    assert hist["counts"] == [3, 0, 1] + [0] * 9 + [1]  # C4, C#4, D4, ..., C5: every note in between too


def test_every_note_gets_a_bin_whatever_max_bins():
    hist = note_histogram(np.arange(30, 100))
    assert len(hist["counts"]) == 70 > MAX_BINS


def test_no_pitches_no_note_histogram():
    assert note_histogram([]) is None
