"""Tests for scripts/audio_headers.py: duration and sample rate from file headers."""

import pytest

import audio_headers
from audio_fakes import (
    make_flac,
    make_mp3_cbr,
    make_mp3_with_id3,
    make_mp3_xing,
    make_wav,
    mp3_frame_header,
    wav_with_odd_junk_chunk,
)


def test_wav_header_duration_and_sample_rate():
    data = make_wav(1.25, 16000, channels=2)
    duration, sample_rate = audio_headers.wav_header(data, len(data))
    assert duration == pytest.approx(1.25)
    assert sample_rate == 16000


def test_wav_header_skips_odd_padded_chunks():
    data = wav_with_odd_junk_chunk()
    assert audio_headers.wav_header(data, len(data)) == (1.0, 8000)


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"not a wave file", "not a WAV"),
        (make_wav()[:36], "no data chunk"),
        (
            b"RIFF\x10\x00\x00\x00WAVE"
            b"data\x04\x00\x00\x00\x00\x00\x00\x00",
            "data chunk before fmt",
        ),
    ],
)
def test_wav_header_rejects_invalid_files(data, message):
    with pytest.raises(ValueError, match=message):
        audio_headers.wav_header(data, len(data))


def test_flac_header_duration_and_sample_rate():
    data = make_flac(2.5, 16000)
    duration, sample_rate = audio_headers.flac_header(data, len(data))
    assert duration == pytest.approx(2.5)
    assert sample_rate == 16000


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"not flac", "not a FLAC"),
        (
            b"fLaC\x81\x00\x00\x22" + bytes(34),
            "first metadata block is not STREAMINFO",
        ),
        (make_flac(0, 16000), "STREAMINFO carries no length"),
    ],
)
def test_flac_header_rejects_invalid_files(data, message):
    with pytest.raises(ValueError, match=message):
        audio_headers.flac_header(data, len(data))


def test_mp3_header_constant_bitrate_uses_file_size():
    data = make_mp3_cbr(2.0)
    duration, sample_rate = audio_headers.mp3_header(data, len(data))
    assert duration == pytest.approx(2.0)
    assert sample_rate == 44100


def test_mp3_header_skips_id3_tag():
    data = make_mp3_with_id3(1.0)
    duration, sample_rate = audio_headers.mp3_header(data, len(data))
    assert duration == pytest.approx(1.0)
    assert sample_rate == 44100


def test_mp3_header_uses_xing_frame_count():
    data = make_mp3_xing(frames=100)
    duration, sample_rate = audio_headers.mp3_header(data, len(data))
    assert duration == pytest.approx(100 * 1152 / 44100)
    assert sample_rate == 44100


@pytest.mark.parametrize(
    ("version", "expected_rate"),
    [(3, 44100), (2, 22050), (0, 11025)],
)
def test_mp3_header_supports_mpeg_versions(version, expected_rate):
    data = mp3_frame_header(version=version, bitrate_index=8) + bytes(100)
    assert audio_headers.mp3_header(data, len(data))[1] == expected_rate


def test_mp3_header_rejects_invalid_file():
    with pytest.raises(ValueError, match="no MPEG frame"):
        audio_headers.mp3_header(b"not an mp3", 10)


def test_parse_header_is_case_insensitive():
    data = make_wav()
    assert audio_headers.parse_header("AUDIO.WAV", data, len(data)) == (1.0, 8000)


def test_parse_header_rejects_unsupported_extension():
    with pytest.raises(ValueError, match=r"no parser for \.ogg"):
        audio_headers.parse_header("audio.ogg", b"", 0)
