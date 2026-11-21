"""Tiny synthetic media + Ad Library JSON for intake tests."""

from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path


def _chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def _minimal_png_bytes(width: int = 8, height: int = 8) -> bytes:
    """Valid RGB PNG with IDAT (blank images without IDAT break Pillow)."""
    raw = b"".join(b"\x00" + (b"\xff\xff\xff" * width) for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(raw, 9))
        + _chunk(b"IEND", b"")
    )


def write_png(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_minimal_png_bytes())
    return path


def write_adlib(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "extractor": "facebook:ads",
                "ad_id": "SYNTHAD999888",
                "page_id": "SYNTHPAGE1122",
                "title": "Synthetic ad",
            }
        ),
        encoding="utf-8",
    )
    return path
