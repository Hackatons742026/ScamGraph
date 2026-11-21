"""Video key-frame extraction with pHash dedup and OCR on kept frames."""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from backend.pipeline.models import MediaRef
from backend.pipeline.ocr import ocr_image

logger = logging.getLogger(__name__)

_PHASH_HAMMING_MAX = 6  # near-identical threshold


@dataclass
class VideoParseResult:
    ok: bool
    error: str | None = None
    frames: list[MediaRef] = field(default_factory=list)


def cache_root() -> Path:
    raw = os.environ.get("SCAMGRAPH_CACHE_DIR") or "data/cache"
    root = Path(raw)
    root.mkdir(parents=True, exist_ok=True)
    (root / "media").mkdir(parents=True, exist_ok=True)
    return root


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def extract_keyframes(
    path: Path | str,
    *,
    artifact_id: str,
    max_frames: int = 40,
) -> VideoParseResult:
    """Extract frames about every 2 s at 720 px height, dedupe by pHash, OCR kept frames.

    Frames are written under ``$SCAMGRAPH_CACHE_DIR/media/<sha256>.jpg``.
    """
    video = Path(path)
    if not video.is_file():
        return VideoParseResult(ok=False, error="file not found")
    if not ffmpeg_available():
        return VideoParseResult(ok=False, error="ffmpeg not available")

    with tempfile.TemporaryDirectory(prefix="sg-frames-") as tmp:
        tmp_dir = Path(tmp)
        pattern = tmp_dir / "frame_%04d.jpg"
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(video),
            "-vf",
            "fps=1/2,scale=-2:720",
            "-frames:v",
            str(max_frames),
            str(pattern),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        except Exception as exc:  # noqa: BLE001
            return VideoParseResult(ok=False, error=f"ffmpeg failed: {exc}"[:200])

        raw_frames = sorted(tmp_dir.glob("frame_*.jpg"))
        kept = _dedupe_frames(raw_frames)
        frames: list[MediaRef] = []
        for idx, frame_path in enumerate(kept):
            digest = hashlib.sha256(frame_path.read_bytes()).hexdigest()
            dest_rel = f"media/{digest}.jpg"
            dest = cache_root() / dest_rel
            if not dest.exists():
                dest.write_bytes(frame_path.read_bytes())
            phash = _phash_hex(frame_path)
            ocr = ocr_image(frame_path)
            frames.append(
                MediaRef(
                    id=f"{artifact_id}_f{idx}",
                    artifact_id=artifact_id,
                    kind="frame",
                    sha256=digest,
                    path=dest_rel.replace("\\", "/"),
                    phash=phash,
                    frame_ts=float(idx * 2),
                    ocr_text=ocr.text or None,
                )
            )
        return VideoParseResult(ok=True, frames=frames)


def _dedupe_frames(paths: list[Path]) -> list[Path]:
    kept: list[Path] = []
    hashes: list[object] = []
    for path in paths:
        h = _phash_obj(path)
        if h is None:
            kept.append(path)
            continue
        if any(_hamming(h, prev) <= _PHASH_HAMMING_MAX for prev in hashes):
            continue
        hashes.append(h)
        kept.append(path)
    return kept


def _phash_obj(path: Path):
    try:
        import imagehash
        from PIL import Image

        return imagehash.phash(Image.open(path))
    except Exception:  # noqa: BLE001
        return None


def _phash_hex(path: Path) -> str | None:
    h = _phash_obj(path)
    return str(h) if h is not None else None


def _hamming(a, b) -> int:
    try:
        return int(a - b)
    except Exception:  # noqa: BLE001
        return 99
