"""Screenshot / image artifact intake with optional OCR."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from backend.pipeline.models import MediaRef, ParseStatus
from backend.pipeline.ocr import ocr_image
from backend.pipeline.video import cache_root


@dataclass
class ImageParseResult:
    parse_status: ParseStatus
    error: str | None = None
    media: MediaRef | None = None
    ocr_engine: str | None = None


def parse_image(
    path: Path | str,
    *,
    artifact_id: str,
    kind: str = "screenshot",
) -> ImageParseResult:
    """Hash image, optionally cache a copy, run OCR. Never raises."""
    try:
        image_path = Path(path)
        if not image_path.is_file():
            return ImageParseResult(
                parse_status=ParseStatus.FAILED,
                error="file not found",
            )

        try:
            from PIL import Image, UnidentifiedImageError
        except ImportError:
            Image = None
            UnidentifiedImageError = OSError
        if Image is not None:
            try:
                with Image.open(image_path) as opened:
                    opened.verify()
            except (UnidentifiedImageError, OSError, ValueError):
                return ImageParseResult(
                    parse_status=ParseStatus.FAILED,
                    error="invalid or unreadable image",
                )

        raw = image_path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        dest_rel = f"media/{digest}{image_path.suffix.lower() or '.bin'}"
        dest = cache_root() / dest_rel
        if not dest.exists():
            dest.write_bytes(raw)

        phash = _phash_hex(image_path)
        ocr = ocr_image(image_path)
        status = ParseStatus.OK
        error = ocr.error
        if ocr.engine is None and ocr.error:
            status = ParseStatus.PARTIAL

        media = MediaRef(
            id=f"{artifact_id}_img",
            artifact_id=artifact_id,
            kind=kind,
            sha256=digest,
            path=dest_rel.replace("\\", "/"),
            phash=phash,
            frame_ts=None,
            ocr_text=ocr.text or None,
        )
        return ImageParseResult(
            parse_status=status,
            error=error,
            media=media,
            ocr_engine=ocr.engine,
        )
    except Exception as exc:  # noqa: BLE001
        return ImageParseResult(
            parse_status=ParseStatus.FAILED,
            error=f"{type(exc).__name__}: {exc}"[:200],
        )


def _phash_hex(path: Path) -> str | None:
    try:
        import imagehash
        from PIL import Image

        return str(imagehash.phash(Image.open(path)))
    except Exception:  # noqa: BLE001
        return None
