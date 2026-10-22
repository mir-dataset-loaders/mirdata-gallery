"""Histograms as {"unit", "edges", "counts"}, with bin widths chosen from the data.

One rule picks the width: the Freedman-Diaconis estimate rounded to 1, 2 or
5 times a power of ten, but never so narrow that there are more than MAX_BINS
bins. log=True gives log-spaced edges instead. Pitches have their own:
note_histogram, one bin per note.
"""

import math

import numpy as np

MAX_BINS = 25
STEP_SIZES = (1, 2, 5)  # bin widths and log-spaced edges are one of these times a power of ten


def tidy_width(raw, up=False):
    """1, 2 or 5 times a power of ten: the closest to raw (in ratio), or with up=True the smallest at or above it.

    e.g. 1.4 -> 1 (up: 2), 37 -> 50 (up: 50), 0.3 -> 0.2 (up: 0.5). Without 2.5,
    every width from 1 up is a whole number.
    """
    if raw <= 0:
        raise ValueError("bin width must be positive")
    scale = 10 ** math.floor(math.log10(raw))
    candidates = [step * scale for step in STEP_SIZES] + [10 * scale]
    if up:
        return min(c for c in candidates if c >= raw * (1 - 1e-9))  # 1e-9: float noise
    return min(candidates, key=lambda c: abs(math.log(c / raw)))


def _number(x):
    """A Python int when x is integral, else a float with float noise removed."""
    x = round(float(x), 10)
    return int(x) if x == int(x) else x


def log_edges(lo, hi):
    """Edges at 1, 2, 5 times powers of ten, from the one at or below lo to the one above hi.

    Falls back to whole decades when that would be more than MAX_BINS bins.
    """
    k_lo, k_hi = math.floor(math.log10(lo)), math.floor(math.log10(hi))
    for steps in (STEP_SIZES, (1,)):
        candidates = sorted(s * 10.0**k for k in range(k_lo, k_hi + 2) for s in steps)
        start = max(c for c in candidates if c <= lo)
        end = min(c for c in candidates if c > hi)
        edges = [c for c in candidates if start <= c <= end]
        if len(edges) - 1 <= MAX_BINS:
            return edges
    return edges


def histogram(values, unit, log=False):
    """{"unit", "edges", "counts"} of the values, or None when there are none.

    counts[i] is the number of values in [edges[i], edges[i + 1]). The width is
    the larger of the Freedman-Diaconis width and the narrowest width that keeps
    to MAX_BINS bins; a single repeated value gets a single bin. With log=True
    the edges are 1, 2, 5 times powers of ten, and values that are not positive
    are left out.
    """
    values = np.asarray([v for v in values if v is not None], dtype=float)
    values = values[np.isfinite(values)]
    if log:
        values = values[values > 0]
    if not len(values):
        return None
    lo, hi = float(values.min()), float(values.max())
    if log:
        edges = log_edges(lo, hi)
        counts, _ = np.histogram(values, bins=edges)
        return {
            "unit": unit,
            "edges": [_number(e) for e in edges],
            "counts": [int(c) for c in counts],
        }
    if hi == lo:  # one repeated value: a single bin around it
        width = tidy_width(abs(lo) / 10) if lo else 1
    else:
        q1, q3 = np.percentile(values, [25, 75])
        fd = 2 * (q3 - q1) / len(values) ** (1 / 3)  # Freedman-Diaconis
        fewest_bins = tidy_width((hi - lo) / MAX_BINS, up=True)
        if math.floor(hi / fewest_bins) - math.floor(lo / fewest_bins) + 1 > MAX_BINS:
            # edges sit on multiples of the width, which can add one bin: the next tidy width
            fewest_bins = tidy_width(fewest_bins * 1.5, up=True)
        # fd is 0 when most values are equal: the bin limit alone decides then
        width = max(tidy_width(fd), fewest_bins) if fd > 0 else fewest_bins

    start = math.floor(lo / width) * width
    end = math.floor(hi / width) * width + width  # every value is in [start, end)
    edges = np.arange(start, end + width / 2, width)
    counts, _ = np.histogram(values, bins=edges)
    return {
        "unit": unit,
        "edges": [_number(e) for e in edges],
        "counts": [int(c) for c in counts],
    }


def note_histogram(midi):
    """{"unit": "midi", "edges", "counts"}: one bin per note, or None when there are none.

    Each MIDI pitch is counted under its nearest whole note, so the edges sit
    between notes (59.5, 60.5, ...): a C5 read from 523.25 Hz (71.99996) and one
    read as 72.0003 land in the same bin. Every note from the lowest to the
    highest gets a bin, MAX_BINS or not: the gallery trims the rare extremes.
    """
    midi = np.asarray(midi, dtype=float)
    notes = np.rint(midi[np.isfinite(midi)]).astype(int)
    if not len(notes):
        return None
    lo = int(notes.min())
    counts = np.bincount(notes - lo)
    return {
        "unit": "midi",
        "edges": [_number(lo - 0.5 + i) for i in range(len(counts) + 1)],
        "counts": [int(c) for c in counts],
    }


def format_histogram(hist):
    """One line for the terminal: '0-2 s: 1, 2-4 s: 2'."""
    if not hist:
        return "-"
    edges, unit = hist["edges"], hist["unit"]
    return ", ".join(
        f"{edges[i]}-{edges[i + 1]} {unit}: {count}"
        for i, count in enumerate(hist["counts"])
    )
