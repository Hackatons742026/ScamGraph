"""Polish OCR — Tesseract ``pol`` default, EasyOCR ``pl`` optional fallback."""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class OcrResult:
    text: str
    engine: str | None
    error: str | None = None


def ocr_image(path: Path | str, *, lang: str = "pol") -> OcrResult:
    """Run OCR on an image. Never raises — returns empty text on failure."""
    image_path = Path(path)
    if not image_path.is_file():
        return OcrResult(text="", engine=None, error="file not found")

    prepared = _preprocess(image_path)
    if prepared is None:
        return OcrResult(text="", engine=None, error="preprocess unavailable")

    tess = _tesseract(prepared, lang=lang)
    if tess is not None:
        return tess

    easy = _easyocr(prepared)
    if easy is not None:
        return easy

    return OcrResult(
        text="",
        engine=None,
        error="no OCR engine available (install tesseract-ocr-pol or easyocr)",
    )


def tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


def pillow_available() -> bool:
    try:
        import PIL  # noqa: F401

        return True
    except ImportError:
        return False


def pytesseract_available() -> bool:
    try:
        import pytesseract  # noqa: F401

        return True
    except ImportError:
        return False


def ocr_stack_available() -> bool:
    """True when Tesseract binary + Pillow + pytesseract are all usable."""
    return tesseract_available() and pillow_available() and pytesseract_available()


def _preprocess(path: Path):
    """Greyscale + 2× upscale. Returns a PIL Image or None."""
    try:
        from PIL import Image, ImageOps
    except ImportError:
        logger.info("Pillow not installed; OCR preprocess skipped")
        return None
    try:
        with Image.open(path) as opened:
            img = ImageOps.grayscale(opened.convert("RGB"))
        w, h = img.size
        if w > 0 and h > 0:
            img = img.resize((max(w * 2, 1), max(h * 2, 1)))
        return img
    except Exception as exc:  # noqa: BLE001
        logger.info("OCR preprocess failed: %s", exc)
        return None


def _tesseract(image, *, lang: str) -> OcrResult | None:
    if not tesseract_available():
        return None
    try:
        import pytesseract
    except ImportError:
        return None
    try:
        text = pytesseract.image_to_string(image, lang=lang) or ""
        return OcrResult(text=text.strip(), engine="tesseract")
    except Exception as exc:  # noqa: BLE001
        # Retry with eng if Polish data missing.
        try:
            import pytesseract

            text = pytesseract.image_to_string(image, lang="eng") or ""
            return OcrResult(
                text=text.strip(),
                engine="tesseract",
                error=f"pol failed ({exc}); used eng",
            )
        except Exception as exc2:  # noqa: BLE001
            return OcrResult(text="", engine="tesseract", error=str(exc2)[:200])


def _easyocr(image) -> OcrResult | None:
    try:
        import easyocr  # type: ignore[import-not-found]
        import numpy as np
    except ImportError:
        return None
    try:
        reader = easyocr.Reader(["pl"], gpu=False, verbose=False)
        arr = np.array(image.convert("RGB"))
        lines = reader.readtext(arr, detail=0, paragraph=True)
        text = " ".join(str(x) for x in lines).strip()
        return OcrResult(text=text, engine="easyocr")
    except Exception as exc:  # noqa: BLE001
        return OcrResult(text="", engine="easyocr", error=str(exc)[:200])
