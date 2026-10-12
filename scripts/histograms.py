"""Histograms with bin widths chosen from the data, in a form that fits in a card.

histogram() turns a list of numbers into {"unit", "edges", "counts"}: the
bin width comes from the Freedman-Diaconis rule, rounded to a step size
(1, 2, 2.5, 5 times a power of ten) and widened until there are at most
MAX_BINS bins, and the edges are multiples of that width. The edges and
counts are plain Python numbers, so the result dumps cleanly to JSON or YAML.

duration_histogram() is the one used for audio durations: seconds for short
clips, minutes once the typical track is longer than MINUTES_FROM seconds.
"""

import math

import numpy as np

MAX_BINS = 20
STEP_SIZES = (1, 2, 2.5, 5)  # bin widths are one of these times a power of ten
MINUTES_FROM = 120  # seconds; a dataset whose median track is longer is binned in minutes


def step_width(raw):
    """The step size closest to raw (in ratio), e.g. 1.4 -> 1, 37 -> 50, 0.3 -> 0.25."""
    if raw <= 0:
        raise ValueError("bin width must be positive")
    scale = 10 ** math.floor(math.log10(raw))
    candidates = [step * scale for step in STEP_SIZES] + [10 * scale]
    return min(candidates, key=lambda c: abs(math.log(c / raw)))


def next_step_width(width):
    """The step size just above a step size: 1 -> 2 -> 2.5 -> 5 -> 10."""
    return min(c for c in (step_width(width * f) for f in (1.5, 2, 2.5, 3)) if c > width)


def _number(x):
    """A Python int when x is integral, else a float with float noise removed."""
    x = round(float(x), 10)
    return int(x) if x == int(x) else x


def histogram(values, unit):
    """{"unit", "edges", "counts"} of the values, or None when there are none.

    edges has one more entry than counts; counts[i] is the number of values
    in [edges[i], edges[i + 1]). The width is the Freedman-Diaconis estimate
    rounded to a step size; when the data has no spread (all values
    equal, or an interquartile range of zero) the Sturges rule or a single
    bin takes over.
    """
    values = np.asarray([v for v in values if v is not None], dtype=float)
    values = values[np.isfinite(values)]
    if not len(values):
        return None
    lo, hi = float(values.min()), float(values.max())
    n = len(values)
    q1, q3 = np.percentile(values, [25, 75])
    if hi == lo:
        width = step_width(abs(lo) / 10) if lo else 1.0
    elif q3 > q1:
        width = step_width(2 * (q3 - q1) / n ** (1 / 3))
    else:
        width = step_width((hi - lo) / math.ceil(math.log2(n) + 1))
    while (math.floor(hi / width) - math.floor(lo / width) + 1) > MAX_BINS:
        width = next_step_width(width)

    start = math.floor(lo / width) * width
    end = math.floor(hi / width) * width + width  # every value is in [start, end)
    edges = np.arange(start, end + width / 2, width)
    counts, _ = np.histogram(values, bins=edges)
    return {
        "unit": unit,
        "edges": [_number(e) for e in edges],
        "counts": [int(c) for c in counts],
    }


def duration_histogram(seconds):
    """Histogram of durations: in seconds, or in minutes when the median is over MINUTES_FROM."""
    seconds = [s for s in seconds if s is not None]
    if not seconds:
        return None
    if np.median(seconds) > MINUTES_FROM:
        return histogram([s / 60 for s in seconds], "min")
    return histogram(seconds, "s")


def format_histogram(hist):
    """One line for the terminal: '0-2 s: 1, 2-4 s: 2'."""
    if not hist:
        return "-"
    edges, unit = hist["edges"], hist["unit"]
    return ", ".join(
        f"{edges[i]}-{edges[i + 1]} {unit}: {count}" for i, count in enumerate(hist["counts"])
    )
