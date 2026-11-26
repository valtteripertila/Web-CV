"""Read common image dimensions using only Python's standard library."""

import re
import struct
import xml.etree.ElementTree as ET
from pathlib import Path


def _jpeg(data):
    if not data.startswith(b"\xff\xd8"):
        return None
    offset = 2
    frame_markers = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
    while offset + 4 <= len(data):
        while offset < len(data) and data[offset] != 0xFF:
            offset += 1
        while offset < len(data) and data[offset] == 0xFF:
            offset += 1
        if offset >= len(data):
            break
        marker = data[offset]
        offset += 1
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            continue
        if offset + 2 > len(data):
            break
        length = struct.unpack_from(">H", data, offset)[0]
        if length < 2 or offset + length > len(data):
            break
        if marker in frame_markers and length >= 7:
            height, width = struct.unpack_from(">HH", data, offset + 3)
            return (width, height) if width and height else None
        offset += length
    return None


def _webp(data):
    if len(data) < 30 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return None
    chunk = data[12:16]
    if chunk == b"VP8X":
        width = 1 + int.from_bytes(data[24:27], "little")
        height = 1 + int.from_bytes(data[27:30], "little")
        return width, height
    if chunk == b"VP8L" and len(data) >= 25 and data[20] == 0x2F:
        b1, b2, b3, b4 = data[21:25]
        width = 1 + b1 + ((b2 & 0x3F) << 8)
        height = 1 + (b2 >> 6) + (b3 << 2) + ((b4 & 0x0F) << 10)
        return width, height
    if chunk == b"VP8 " and len(data) >= 30 and data[23:26] == b"\x9d\x01\x2a":
        width = struct.unpack_from("<H", data, 26)[0] & 0x3FFF
        height = struct.unpack_from("<H", data, 28)[0] & 0x3FFF
        return (width, height) if width and height else None
    return None


def _svg(path):
    root = ET.parse(path).getroot()

    def number(value):
        match = re.match(r"\s*(\d+(?:\.\d+)?)", value or "")
        if not match:
            return None
        result = round(float(match.group(1)))
        return result if result > 0 else None

    width, height = number(root.attrib.get("width")), number(root.attrib.get("height"))
    if width and height:
        return width, height
    view_box = root.attrib.get("viewBox") or root.attrib.get("viewbox") or ""
    values = re.split(r"[\s,]+", view_box.strip())
    if len(values) == 4:
        width, height = number(values[2]), number(values[3])
        if width and height:
            return width, height
    return None


def image_dimensions(path):
    """Return (width, height), or None when the image header is unsupported or invalid."""
    path = Path(path)
    extension = path.suffix.lower()
    if extension == ".svg":
        try:
            return _svg(path)
        except (ET.ParseError, OSError):
            return None
    data = path.read_bytes()
    if extension == ".png" and data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        width, height = struct.unpack_from(">II", data, 16)
        return (width, height) if width and height else None
    if extension == ".gif" and data[:6] in (b"GIF87a", b"GIF89a") and len(data) >= 10:
        width, height = struct.unpack_from("<HH", data, 6)
        return (width, height) if width and height else None
    if extension in (".jpg", ".jpeg"):
        return _jpeg(data)
    if extension == ".webp":
        return _webp(data)
    if extension == ".avif":
        marker = data.find(b"ispe")
        if marker >= 0 and marker + 16 <= len(data):
            width, height = struct.unpack_from(">II", data, marker + 8)
            return (width, height) if width and height else None
    return None
