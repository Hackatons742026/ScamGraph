"""Build a synthetic incident tree covering all 9 artifact types.

Never contains real NASK data — safe to commit.
"""

from __future__ import annotations

import json
from pathlib import Path

# Minimal valid-looking HAR (not streamed here — discovery only needs the file).
_MIN_HAR = json.dumps(
    {
        "log": {
            "version": "1.2",
            "creator": {"name": "synthetic", "version": "1"},
            "entries": [],
        }
    }
)

_ADLIB = {
    "extractor": "facebook:ads",
    "ad_id": "synthetic-ad-001",
    "page_id": "synthetic-page-001",
    "title": "Synthetic Ad Library entry",
}

_MANIFEST = {
    "url": "https://example.test/landing?fbclid=SYNTHETIC",
    "captured_at": "2026-01-01T00:00:00Z",
}


def build_synthetic_dataset(root: Path) -> Path:
    """Create ``root/incident_alpha`` with every discoverable artifact kind.

    Returns the dataset root (same as ``root``).
    """
    root.mkdir(parents=True, exist_ok=True)
    incident = root / "incident_alpha"
    incident.mkdir(parents=True, exist_ok=True)

    # 1) Top-level HAR
    (incident / "capture.har").write_text(_MIN_HAR, encoding="utf-8")

    # 2) Hidden .har
    (incident / ".har").write_text(_MIN_HAR, encoding="utf-8")

    # 3) Saved page + _files/
    page = incident / "offer.html"
    page.write_text(
        "<!doctype html><html><head><title>Synthetic offer</title></head>"
        "<body><h1>Offer</h1><a href='https://example.test/x?token=abc'>x</a></body></html>",
        encoding="utf-8",
    )
    files_dir = incident / "offer_files"
    files_dir.mkdir(exist_ok=True)
    (files_dir / "script.js").write_text("console.log('synthetic');", encoding="utf-8")

    # 4) MHTML
    (incident / "saved.mhtml").write_text(
        "From: <saved@localhost>\r\nMIME-Version: 1.0\r\nContent-Type: multipart/related; "
        'boundary="BOUNDARY"\r\n\r\n--BOUNDARY\r\nContent-Type: text/html\r\n\r\n'
        "<html><body>mhtml</body></html>\r\n--BOUNDARY--\r\n",
        encoding="utf-8",
    )

    # 5) Capture bundle
    bundle = incident / "capture_bundle"
    bundle.mkdir(exist_ok=True)
    (bundle / "manifest.json").write_text(json.dumps(_MANIFEST), encoding="utf-8")
    (bundle / "dom.html").write_text("<html><body>dom</body></html>", encoding="utf-8")
    (bundle / "page.har").write_text(_MIN_HAR, encoding="utf-8")
    (bundle / "resources").mkdir(exist_ok=True)
    (bundle / "resources" / "x.png").write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    # 6) Screenshot
    (incident / "screen_desktop.png").write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    # 7) Video placeholder (tiny bytes; extension is what discovery uses)
    (incident / "clip.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42synthetic")

    # 8) Ad Library info.json
    (incident / "ad.info.json").write_text(json.dumps(_ADLIB), encoding="utf-8")

    # 9) Funnel sub-folders with nested artifacts
    for idx, name in enumerate(("strona_1", "strona_2", "strona_3"), start=1):
        step = incident / name
        step.mkdir(exist_ok=True)
        (step / f"step{idx}.html").write_text(
            f"<html><body>step {idx}</body></html>", encoding="utf-8"
        )
        if idx == 1:
            (step / "step1.har").write_text(_MIN_HAR, encoding="utf-8")

    # Second incident to prove multi-incident discovery (sparse)
    other = root / "incident_beta"
    other.mkdir(exist_ok=True)
    (other / "only.png").write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    return root
