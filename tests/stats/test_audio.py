"""stats/audio.py: what one dataset's index says about its audio.

The indexes here are written by hand, so the numbers show in the test itself.
"""

import pytest

from stats.annotation_types import grid
from stats.audio import dataset_stats


def track(name, **audio):
    """An index entry with one audio file per keyword: audio_key=(seconds, sample rate)."""
    entry = {key: [f"{name}_{key}.wav", "md5"] for key in audio}
    entry["audio_features"] = {
        key: {"duration_seconds": seconds, "sample_rate": rate, "num_channels": 1}
        for key, (seconds, rate) in audio.items()
    }
    return entry


def test_dataset_stats():
    index = {
        "tracks": {
            "a": track("a", audio=(2.5, 44100)),
            "b": track("b", audio=(3.25, 44100)),
            "c": track("c", audio=(1.75, 48000)),
        },
        # wrong on purpose: only the tracks count
        "audio_summary": {
            "file_count": 99,
            "total_audio_duration_seconds": 9999.0,
            "sample_rate_counts": {"8000": 99},
            "channel_counts": {"2": 99},
        },
    }
    result = dataset_stats(index)
    fields = {
        "status",
        "problems",
        "n_tracks",
        "n_audio_files",
        "total_seconds",
        "sample_rates",
        "durations",
    }
    assert set(result) == fields, "the result should have exactly its fields"
    assert result["status"] == "ok", "status should be ok when the index can be read"
    assert result["problems"] == [], "a readable index should report no problems"
    assert result["n_tracks"] == 3, "n_tracks should count every track in the index"
    assert result["n_audio_files"] == 3, "n_audio_files should count every audio file"
    assert (
        result["total_seconds"] == 7.5
    ), "total_seconds should add up the tracks' durations, not audio_summary's total"
    sample_rates = {"44.1k": 2, "48k": 1}
    assert (
        result["sample_rates"] == sample_rates
    ), "sample_rates should count the tracks at each rate, not audio_summary's counts"
    durations = grid([2.5, 3.25, 1.75], "s")
    assert (
        result["durations"] == durations
    ), "durations should be the grid of the tracks' durations, in seconds"


def test_dataset_stats_total_rounded():
    index = {
        "tracks": {
            "a": track("a", audio=(1.24, 44100)),
            "b": track("b", audio=(1.24, 44100)),
        }
    }
    assert (
        dataset_stats(index)["total_seconds"] == 2.5
    ), "total_seconds should add the exact durations, then round to one decimal"


def test_dataset_stats_multiple_audio():
    index = {
        "tracks": {
            "a": track(
                "a",
                audio_hex=(2.5, 44100),
                audio_mic=(2.5, 44100),
                audio_mix=(2.5, 44100),
            ),
            "b": track("b", audio=(3.5, 44100)),
        }
    }
    result = dataset_stats(index)
    assert result["n_tracks"] == 2, "n_tracks should count a track once"
    assert result["n_audio_files"] == 4, "n_audio_files should still count every file"
    assert (
        result["total_seconds"] == 6.0
    ), "audio files that agree should add one duration to the total"
    sample_rates = {"44.1k": 2}
    assert (
        result["sample_rates"] == sample_rates
    ), "audio files that agree should count as one track at their rate"
    durations = grid([2.5, 3.5], "s")
    assert (
        result["durations"] == durations
    ), "audio files that agree should put one duration in the grid"


def test_dataset_stats_durations_disagree():
    index = {
        "tracks": {
            "track_a": track("track_a", audio=(2.5, 44100)),
            "track_b": track(
                "track_b", audio_mic=(3.25, 44100), audio_mix=(3.251, 44100)
            ),
        }
    }
    with pytest.raises(ValueError, match="track_b"):
        dataset_stats(index)


def test_dataset_stats_sample_rates_disagree():
    index = {
        "tracks": {
            "track_a": track("track_a", audio=(2.5, 44100)),
            "track_b": track(
                "track_b", audio_mic=(3.25, 44100), audio_mix=(3.25, 48000)
            ),
        }
    }
    with pytest.raises(ValueError, match="track_b"):
        dataset_stats(index)


def test_dataset_stats_track_without_audio():
    no_audio = {"midi": ["b.mid", "md5"], "audio": [None, None], "audio_features": {}}
    index = {"tracks": {"a": track("a", audio=(2.5, 44100)), "b": no_audio}}
    result = dataset_stats(index)
    assert result["n_tracks"] == 2, "n_tracks should count a track without audio"
    assert result["n_audio_files"] == 1, "n_audio_files should count only real files"
    assert (
        result["total_seconds"] == 2.5
    ), "a track without audio should add nothing to the total"
    sample_rates = {"44.1k": 1}
    assert (
        result["sample_rates"] == sample_rates
    ), "a track without audio should not be counted at any rate"
    durations = grid([2.5], "s")
    assert (
        result["durations"] == durations
    ), "a track without audio should not be in the grid"


def test_dataset_stats_no_audio_features():
    index = {"tracks": {"a": {"audio": ["a.wav", "md5"]}}}
    result = dataset_stats(index)
    assert result["status"] == "ok", "an index without audio features is not an error"
    assert result["n_tracks"] == 1, "n_tracks should still count the tracks"
    assert result["n_audio_files"] == 1, "n_audio_files should still count the files"
    assert result["total_seconds"] is None, "no durations should give a null total"
    assert result["sample_rates"] is None, "no sample rates should give null"
    assert result["durations"] is None, "no durations should give a null grid"


def test_dataset_stats_sample_rate_labels():
    labels = {
        8000: "8k",
        11025: "11.025k",
        16000: "16k",
        22050: "22.05k",
        24000: "24k",
        32000: "32k",
        44100: "44.1k",
        48000: "48k",
    }
    index = {
        "tracks": {str(rate): track(str(rate), audio=(1.0, rate)) for rate in labels}
    }
    sample_rates = {label: 1 for label in labels.values()}
    assert (
        dataset_stats(index)["sample_rates"] == sample_rates
    ), "a sample rate should be labelled in kHz with a k, without extra zeros"
