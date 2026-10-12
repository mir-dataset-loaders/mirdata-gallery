"""Fake audio files, zip archives and HTTP sessions for the audio_stats tests.

Everything the tests feed to the scripts is built here, byte by byte, so no
test needs a real dataset or the network.
"""

import io
import re
import struct
import wave
import zipfile
from types import SimpleNamespace

import requests

FAKE_URL = "https://example.test/fake_audio.zip"


def make_wav(seconds=1.0, sample_rate=8000, channels=1):
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(b"\x00\x00" * int(seconds * sample_rate) * channels)
    return output.getvalue()


def wav_with_odd_junk_chunk():
    data = make_wav()
    junk = b"JUNK" + struct.pack("<I", 3) + b"abc" + b"\x00"
    riff_size = struct.unpack("<I", data[4:8])[0] + len(junk)
    return data[:4] + struct.pack("<I", riff_size) + data[8:12] + junk + data[12:]


def make_flac(seconds=1.0, sample_rate=16000):
    total_samples = int(seconds * sample_rate)
    streaminfo = bytearray(34)
    packed = (
        (sample_rate << 44)
        | (0 << 41)  # one channel
        | (15 << 36)  # 16 bits per sample minus one
        | total_samples
    )
    streaminfo[10:18] = packed.to_bytes(8, "big")
    return b"fLaC" + b"\x80\x00\x00\x22" + bytes(streaminfo)


def mp3_frame_header(version=3, bitrate_index=9, sample_rate_index=0, mono=False):
    byte_1 = 0xE0 | (version << 3) | (1 << 1) | 1
    byte_2 = bitrate_index << 4 | sample_rate_index << 2
    byte_3 = 0xC0 if mono else 0
    return bytes((0xFF, byte_1, byte_2, byte_3))


def make_mp3_cbr(seconds=1.0, bitrate=128000):
    size = int(seconds * bitrate / 8)
    return mp3_frame_header() + b"\x00" * (size - 4)


def syncsafe(value):
    return bytes(
        (
            (value >> 21) & 0x7F,
            (value >> 14) & 0x7F,
            (value >> 7) & 0x7F,
            value & 0x7F,
        )
    )


def make_mp3_with_id3(seconds=1.0):
    payload = b"abcde"
    tag = b"ID3\x04\x00\x00" + syncsafe(len(payload)) + payload
    return tag + make_mp3_cbr(seconds)


def make_mp3_xing(frames=100):
    data = bytearray(48)
    data[:4] = mp3_frame_header()
    xing = 4 + 32
    data[xing : xing + 4] = b"Xing"
    data[xing + 4 : xing + 8] = struct.pack(">I", 1)
    data[xing + 8 : xing + 12] = struct.pack(">I", frames)
    return bytes(data)


def zip_bytes(files, compression=zipfile.ZIP_DEFLATED, prefix=""):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for path, data in files.items():
            archive.writestr(
                f"{prefix}{path}",
                data,
                compress_type=compression,
            )
    return output.getvalue()


class BytesHTTP:
    def __init__(self, data):
        self.data = data

    def read_at(self, offset, size):
        return self.data[offset : offset + size]


class FakeResponse:
    def __init__(self, status_code, content=b"", headers=None, url=FAKE_URL):
        self.status_code = status_code
        self.content = content
        self.headers = headers or {}
        self.url = url
        self.closed = False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def close(self):
        self.closed = True


class FakeRangeSession:
    def __init__(
        self,
        blobs,
        *,
        include_length=True,
        ignore_range=False,
        short_range=False,
        include_content_range=True,
    ):
        self.blobs = blobs
        self.include_length = include_length
        self.ignore_range = ignore_range
        self.short_range = short_range
        self.include_content_range = include_content_range
        self.calls = []

    def mount(self, prefix, adapter):
        pass

    def request(self, method, url, timeout, **kwargs):
        self.calls.append((method, url, kwargs))
        blob = self.blobs[url]

        if method == "HEAD":
            headers = {}
            if self.include_length:
                headers["Content-Length"] = str(len(blob))
            return FakeResponse(200, headers=headers, url=url)

        if self.ignore_range:
            return FakeResponse(200, content=blob, url=url)

        range_header = kwargs.get("headers", {}).get("Range")
        match = re.fullmatch(r"bytes=(\d+)-(\d+)", range_header or "")
        if not match:
            raise AssertionError(f"invalid Range header: {range_header!r}")

        start, end = map(int, match.groups())
        content = blob[start : end + 1]
        if self.short_range and content:
            content = content[:-1]

        headers = {}
        if self.include_content_range:
            headers["Content-Range"] = f"bytes {start}-{end}/{len(blob)}"
        return FakeResponse(206, content=content, headers=headers, url=url)


def fake_remote(filename="fake_audio.zip", url=FAKE_URL, destination_dir=None):
    return SimpleNamespace(
        filename=filename,
        url=url,
        destination_dir=destination_dir,
    )
