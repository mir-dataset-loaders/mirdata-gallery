"""Duration and sample rate of an audio file from its first bytes.

WAV, FLAC and MP3 all announce their length near the start of the file: the
data chunk size, the STREAMINFO sample count, the Xing frame count or the
bitrate. So HEADER_BYTES from the start of a file are enough, and the audio
itself is never decoded. read_file() reads them from disk, read_member() out
of a remote zip (see stats/remote_zip.py).
"""

import os
import struct

from stats import remote_zip

HEADER_BYTES = 64 * 1024  # how much of each audio file we read: enough for any header


def wav_header(data, file_size):
    """(seconds, sample rate) from a RIFF/WAVE header: data chunk size / bytes per second."""
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError("not a WAV file")
    pos, sample_rate, byte_rate = 12, None, None
    while pos + 8 <= len(data):
        chunk_id = data[pos : pos + 4]
        size = struct.unpack("<I", data[pos + 4 : pos + 8])[0]
        if chunk_id == b"fmt ":
            sample_rate, byte_rate = struct.unpack("<II", data[pos + 12 : pos + 20])
        elif chunk_id == b"data":
            if not byte_rate:
                raise ValueError("data chunk before fmt chunk")
            return size / byte_rate, sample_rate
        pos += 8 + size + (size & 1)
    raise ValueError("no data chunk in the first 64 KB")


def flac_header(data, file_size):
    """(seconds, sample rate) from the STREAMINFO block that starts every FLAC file."""
    if data[:4] != b"fLaC":
        raise ValueError("not a FLAC file")
    if data[4] & 0x7F != 0:
        raise ValueError("first metadata block is not STREAMINFO")
    info = data[8:42]
    sample_rate = (info[10] << 12) | (info[11] << 4) | (info[12] >> 4)
    total_samples = ((info[13] & 0x0F) << 32) | int.from_bytes(info[14:18], "big")
    if not sample_rate or not total_samples:
        raise ValueError("STREAMINFO carries no length")
    return total_samples / sample_rate, sample_rate


MP3_BITRATES = {  # kbps for Layer III, by MPEG version then bitrate index
    True: (0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320),
    False: (0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160),
}
MP3_SAMPLE_RATES = {3: (44100, 48000, 32000), 2: (22050, 24000, 16000), 0: (11025, 12000, 8000)}


def mp3_header(data, file_size):
    """(seconds, sample rate) from the first MPEG frame.

    Variable-bitrate files carry a Xing/Info header with the frame count;
    otherwise the file is constant bitrate and duration is size / bitrate.
    """
    pos = 0
    if data[:3] == b"ID3":  # skip the ID3v2 tag at the start
        size = 0
        for b in data[6:10]:
            size = (size << 7) | (b & 0x7F)
        pos = 10 + size + (10 if data[5] & 0x10 else 0)
    while pos + 4 <= len(data):
        b1, b2, b3 = data[pos + 1], data[pos + 2], data[pos + 3]
        if data[pos] == 0xFF and b1 & 0xE0 == 0xE0:
            version = (b1 >> 3) & 3  # 3: MPEG-1, 2: MPEG-2, 0: MPEG-2.5
            layer = (b1 >> 1) & 3  # 1: Layer III
            bitrate_index, rate_index = b2 >> 4, (b2 >> 2) & 3
            if version != 1 and layer == 1 and 0 < bitrate_index < 15 and rate_index < 3:
                break
        pos += 1
    else:
        raise ValueError("no MPEG frame in the first 64 KB")
    mpeg1 = version == 3
    bitrate = MP3_BITRATES[mpeg1][bitrate_index] * 1000
    sample_rate = MP3_SAMPLE_RATES[version][rate_index]
    mono = (b3 >> 6) == 3
    xing = pos + 4 + ((17 if mono else 32) if mpeg1 else (9 if mono else 17))
    if data[xing : xing + 4] in (b"Xing", b"Info"):
        flags = struct.unpack(">I", data[xing + 4 : xing + 8])[0]
        if flags & 1:
            frames = struct.unpack(">I", data[xing + 8 : xing + 12])[0]
            return frames * (1152 if mpeg1 else 576) / sample_rate, sample_rate
    return (file_size - pos) * 8 / bitrate, sample_rate


PARSERS = {".wav": wav_header, ".flac": flac_header, ".mp3": mp3_header}


def parse_header(path, data, file_size):
    """(seconds, sample rate) of an audio file given its first bytes and its size."""
    ext = os.path.splitext(path)[1].lower()
    if ext not in PARSERS:
        raise ValueError(f"no parser for {ext}")
    return PARSERS[ext](data, file_size)


def read_member(http, info):
    """(seconds, sample rate) of one audio file inside a remote zip."""
    head = remote_zip.member_head(http, info, HEADER_BYTES)
    return parse_header(info.filename, head, info.file_size)


def read_file(path):
    """(seconds, sample rate) of one audio file on disk; reads only its first HEADER_BYTES."""
    with open(path, "rb") as f:
        return parse_header(path, f.read(HEADER_BYTES), os.path.getsize(path))
