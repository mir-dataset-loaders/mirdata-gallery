"""The bin rules of stats/histograms.py.

Other test files compare against histogram() and note_histogram(); the exact
bins are checked only here, by hand.
"""

import math

import numpy as np
import pytest

from stats.histograms import MAX_BINS, histogram, log_edges, note_histogram, tidy_width


def test_histogram():
    # 1 to 20: quartiles 5.75 and 15.25, so the Freedman-Diaconis width is
    # 2 * 9.5 / 20 ** (1/3) = 7.0, rounded to the closest tidy width, 5.
    result = histogram(range(1, 21), "s")
    expected = {"unit": "s", "edges": [0, 5, 10, 15, 20, 25], "counts": [4, 5, 5, 5, 1]}
    assert result == expected, (
        "the width should be the Freedman-Diaconis estimate rounded to 1, 2 or 5 times a"
        " power of ten; edges on multiples of it, from below the smallest value to above"
        " the largest; each count covers [edge, next edge)"
    )
    assert all(
        isinstance(edge, int) for edge in result["edges"]
    ), "whole-number edges should be ints"


def test_histogram_empty():
    assert histogram([], "s") is None, "no values should give no histogram"
    missing = [None, float("nan"), float("inf")]
    assert histogram(missing, "s") is None, "None, NaN and infinity should be left out"


def test_histogram_one_value():
    expected = {"unit": "s", "edges": [7, 7.5], "counts": [3]}
    assert (
        histogram([7, 7, 7], "s") == expected
    ), "one repeated value should get a single bin, a tidy tenth of the value wide"
    expected = {"unit": "s", "edges": [0, 1], "counts": [2]}
    assert (
        histogram([0, 0], "s") == expected
    ), "a repeated 0 should get a single bin of width 1"


def test_histogram_bin_limit():
    # 100 values between 0 and 1 and one at 1000: the Freedman-Diaconis width of
    # the crowd (about 0.2) would need thousands of bins to reach 1000.
    values = [i / 100 for i in range(100)] + [1000]
    result = histogram(values, "s")
    n_bins = len(result["counts"])
    assert n_bins <= MAX_BINS, f"there should never be more than {MAX_BINS} bins"
    width = result["edges"][1] - result["edges"][0]
    assert width == 50, "the bin limit should pick the narrowest tidy width that fits"
    assert sum(result["counts"]) == 101, "every value should be counted"

    mostly_equal = [5] * 20 + [6, 100]  # quartiles equal: Freedman-Diaconis width 0
    result = histogram(mostly_equal, "s")
    assert (
        len(result["counts"]) <= MAX_BINS
    ), "a width of 0 should leave the choice to the bin limit"
    assert sum(result["counts"]) == 22, "every value should be counted"


def test_histogram_float_noise():
    result = histogram([0.1, 0.2, 0.3], "s")
    for edge in result["edges"]:
        assert edge == round(edge, 10), f"edge {edge!r} should carry no float noise"


def test_histogram_log():
    result = histogram([3, 70, 0, -5], "s", log=True)
    edges, counts = [2, 5, 10, 20, 50, 100], [1, 0, 0, 0, 1]
    expected = {"unit": "s", "edges": edges, "counts": counts}
    assert result == expected, (
        "log edges should be 1, 2 or 5 times a power of ten, from the one at or below the"
        " smallest value to the one above the largest; 0 and below should be left out"
    )
    assert (
        histogram([0, -5], "s", log=True) is None
    ), "no positive values should give no log histogram"


def test_tidy_width():
    closest = {1.4: 1, 37: 50, 0.3: 0.2, 2: 2}
    for raw, width in closest.items():
        rounded = tidy_width(raw)
        assert rounded == pytest.approx(width), f"{raw} should round to {width}"
    at_or_above = {1.4: 2, 37: 50, 0.3: 0.5, 2: 2}
    for raw, width in at_or_above.items():
        rounded = tidy_width(raw, up=True)
        assert rounded == pytest.approx(width), f"{raw} should round up to {width}"
    with pytest.raises(ValueError):
        tidy_width(0)


def test_log_edges():
    edges = log_edges(3, 70)
    expected = pytest.approx([2, 5, 10, 20, 50, 100])
    assert (
        edges == expected
    ), "edges should be 1, 2, 5 times powers of ten around the values"
    edges = log_edges(0.001, 1e6)
    decades = pytest.approx([10.0**k for k in range(-3, 8)])
    assert (
        edges == decades
    ), f"a range that would need more than {MAX_BINS} bins should fall back to whole decades"


def test_note_histogram():
    result = note_histogram([71.99996, 72.0003, 60, 60.4])
    edges = [n - 0.5 for n in range(60, 74)]  # 59.5, 60.5, ... 72.5
    counts = [2] + [0] * 11 + [2]
    assert result == {"unit": "midi", "edges": edges, "counts": counts}, (
        "there should be one bin per note, edges halfway between notes, each pitch counted"
        " under its nearest note, and an empty bin for every note in between"
    )
    wide = note_histogram([20, 100])
    assert (
        len(wide["counts"]) == 81
    ), f"notes should get a bin each, more than {MAX_BINS} if needed"
    assert note_histogram([]) is None, "no pitches should give no histogram"
    assert note_histogram([math.nan]) is None, "NaN pitches should be left out"
    single = note_histogram(np.array([60.0]))
    assert single["counts"] == [1], "a numpy array should work too"
