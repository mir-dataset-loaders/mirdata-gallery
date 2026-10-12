"""Tests for scripts/histograms.py: bin width choice, edges, units."""

import pytest

import histograms


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (1.4, 1),
        (1.387, 1),
        (1.8, 2),
        (2.3, 2.5),
        (37, 50),
        (0.3, 0.25),
        (8, 10),
        (120, 100),
    ],
)
def test_step_width(raw, expected):
    assert histograms.step_width(raw) == expected


def test_step_width_rejects_nonpositive():
    with pytest.raises(ValueError):
        histograms.step_width(0)


@pytest.mark.parametrize(
    ("width", "expected"),
    [(1, 2), (2, 2.5), (2.5, 5), (5, 10), (10, 20), (0.5, 1)],
)
def test_next_step_width(width, expected):
    assert histograms.next_step_width(width) == expected


def test_histogram_of_fake_dataset_durations():
    assert histograms.histogram([1.0, 2.5, 3.0], "s") == {
        "unit": "s",
        "edges": [1, 2, 3, 4],
        "counts": [1, 1, 1],
    }


def test_histogram_empty_and_non_finite():
    assert histograms.histogram([], "s") is None
    assert histograms.histogram([None, float("nan")], "s") is None


def test_histogram_single_value_is_one_bin():
    hist = histograms.histogram([30.0], "s")
    assert hist["counts"] == [1]
    assert hist["edges"][0] <= 30 < hist["edges"][1]


def test_histogram_all_equal_values():
    hist = histograms.histogram([30.0] * 50, "s")
    assert hist["counts"] == [50]
    assert hist["edges"][0] <= 30 < hist["edges"][1]


def test_histogram_zero_iqr_but_spread_uses_sturges():
    # 48 clips of 30 s and two outliers: the interquartile range is zero.
    values = [30.0] * 48 + [10.0, 70.0]
    hist = histograms.histogram(values, "s")
    assert sum(hist["counts"]) == 50
    assert hist["edges"][0] <= 10 and hist["edges"][-1] > 70
    assert 2 <= len(hist["counts"]) <= histograms.MAX_BINS


def test_histogram_caps_number_of_bins():
    values = list(range(0, 1000))  # wide spread, many points
    hist = histograms.histogram(values, "s")
    assert len(hist["counts"]) <= histograms.MAX_BINS
    assert sum(hist["counts"]) == 1000
    assert hist["edges"][0] <= 0 and hist["edges"][-1] > 999


def test_histogram_edges_are_plain_numbers():
    hist = histograms.histogram([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8], "s")
    assert all(isinstance(e, (int, float)) for e in hist["edges"])
    assert all(isinstance(c, int) for c in hist["counts"])
    assert all(str(e).count("0000") == 0 for e in hist["edges"])  # no float noise


def test_histogram_log_edges_are_1_2_5_per_decade():
    hist = histograms.histogram([0.001, 0.05, 2.0, 73.0], "s", log=True)
    assert hist["edges"] == [
        0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100
    ]
    assert sum(hist["counts"]) == 4
    assert hist["counts"][0] == 1  # 0.001 sits on the first edge, which is inclusive
    assert hist["counts"][-1] == 1  # 73 is in [50, 100)


def test_histogram_log_drops_nonpositive_values():
    hist = histograms.histogram([0.0, -1.0, 3.0], "s", log=True)
    assert hist["edges"] == [2, 5]
    assert hist["counts"] == [1]
    assert histograms.histogram([0.0, -1.0], "s", log=True) is None


def test_histogram_log_falls_back_to_decades_when_too_wide():
    hist = histograms.histogram([1e-4, 1e4], "s", log=True)  # 8 decades: 24 fine bins
    assert hist["edges"] == [0.0001, 0.001, 0.01, 0.1, 1, 10, 100, 1000, 10000, 100000]
    assert len(hist["counts"]) <= histograms.MAX_BINS


def test_duration_histogram_short_clips_in_seconds():
    hist = histograms.duration_histogram([29.9, 30.0, 30.1, 30.0, 29.8])
    assert hist["unit"] == "s"
    assert sum(hist["counts"]) == 5


def test_duration_histogram_long_tracks_in_minutes():
    seconds = [180, 200, 240, 300, 360, 420, 600, 900]
    hist = histograms.duration_histogram(seconds)
    assert hist["unit"] == "min"
    assert hist["edges"][0] <= 3 and hist["edges"][-1] > 15
    assert sum(hist["counts"]) == 8


def test_duration_histogram_outlier_does_not_switch_to_minutes():
    hist = histograms.duration_histogram([30.0] * 20 + [1200.0])
    assert hist["unit"] == "s"


def test_duration_histogram_empty():
    assert histograms.duration_histogram([]) is None


def test_format_histogram():
    hist = {"unit": "s", "edges": [1, 2, 3, 4], "counts": [1, 1, 1]}
    assert histograms.format_histogram(hist) == "1-2 s: 1, 2-3 s: 1, 3-4 s: 1"
    assert histograms.format_histogram(None) == "-"
