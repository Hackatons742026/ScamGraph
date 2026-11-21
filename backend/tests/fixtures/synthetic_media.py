"""Tiny synthetic media + Ad Library JSON for intake tests."""

from __future__ import annotations

import json
from pathlib import Path

_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x00IEND\xaeB`\x82"
)


def write_png(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_PNG)
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
