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
                error="Image file not found.",
            )

        raw = image_path.read_bytes()
        try:
            from PIL import Image
        except ImportError:
            # Pillow is a normal dependency, but retain the image if an unusually
            # minimal runtime omits it; pHash/OCR will soft-fail below.
            pass
        else:
            try:
                with Image.open(image_path) as opened:
                    opened.load()
            except Exception:  # noqa: BLE001 — malformed uploads must not escape intake
                return ImageParseResult(
                    parse_status=ParseStatus.FAILED,
                    error="Image could not be decoded. Upload a valid PNG, JPEG, or WEBP image.",
                )

        digest = hashlib.sha256(raw).hexdigest()
        dest_rel = f"media/{digest}{image_path.suffix.lower() or '.bin'}"
        dest = cache_root() / dest_rel
        if not dest.exists():
            dest.write_bytes(raw)

        phash = _phash_hex(image_path)
        ocr = ocr_image(image_path)
        status = ParseStatus.PARTIAL if ocr.engine is None or ocr.error else ParseStatus.OK
        error = ocr.error or ("OCR engine unavailable" if ocr.engine is None else None)

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
    except Exception:  # noqa: BLE001 — exception messages can contain local paths
        return ImageParseResult(
            parse_status=ParseStatus.FAILED,
            error="Image processing failed. Verify the file and try again.",
        )


def _phash_hex(path: Path) -> str | None:
    try:
        import imagehash
        from PIL import Image

        return str(imagehash.phash(Image.open(path)))
    except Exception:  # noqa: BLE001
        return None
