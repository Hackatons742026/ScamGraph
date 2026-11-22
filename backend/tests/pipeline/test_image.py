from pathlib import Path

import pytest

pytest.importorskip("PIL.Image")
imagehash = pytest.importorskip("imagehash")
from PIL import Image
from PIL import ImageDraw, ImageFont

from backend.pipeline.intake.image import _phash_hex, parse_image
from backend.pipeline.models import ParseStatus
from backend.pipeline.ocr import OcrResult, ocr_stack_available, tesseract_available


@pytest.fixture(autouse=True)
def _cache_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("SCAMGRAPH_CACHE_DIR", str(tmp_path / "cache"))


@pytest.mark.parametrize(
    ("image_format", "suffix"),
    [("WEBP", ".webp"), ("PNG", ".png"), ("JPEG", ".jpg")],
)
def test_valid_image_formats_keep_phash_and_media_when_optional_ocr_fails(
    image_format, suffix, tmp_path, monkeypatch
):
    path = tmp_path / f"synthetic{suffix}"
    Image.new("RGB", (160, 80), "white").save(path, format=image_format)
    monkeypatch.setattr(
        "backend.pipeline.intake.image.ocr_image",
        lambda _path: OcrResult(text="", engine=None, error="no OCR engine available"),
    )

    result = parse_image(path, artifact_id=f"synthetic-{image_format.lower()}")

    assert result.parse_status == ParseStatus.PARTIAL
    assert result.error == "no OCR engine available"
    assert result.media is not None
    assert result.media.phash == str(imagehash.phash(Image.open(path)))
    assert result.media.path
    assert (tmp_path / "cache" / result.media.path).read_bytes() == path.read_bytes()


def test_polish_fallback_keeps_image_as_partial(tmp_path, monkeypatch):
    path = tmp_path / "synthetic.webp"
    Image.new("RGB", (160, 80), "white").save(path, format="WEBP")
    monkeypatch.setattr(
        "backend.pipeline.intake.image.ocr_image",
        lambda _path: OcrResult(text="synthetic text", engine="tesseract",
                                error="pol failed; used eng"),
    )

    result = parse_image(path, artifact_id="synthetic-polish-fallback")

    assert result.parse_status == ParseStatus.PARTIAL
    assert result.media is not None and result.media.ocr_text == "synthetic text"
    assert result.media.phash == _phash_hex(path)


def test_malformed_image_fails_without_caching_or_exposing_local_path(tmp_path, monkeypatch):
    path = tmp_path / "synthetic-malformed.webp"
    path.write_bytes(b"synthetic bytes, not an image")
    monkeypatch.setattr(
        "backend.pipeline.intake.image.ocr_image",
        lambda _path: pytest.fail("OCR must not run for an invalid image"),
    )

    result = parse_image(path, artifact_id="synthetic-malformed")

    assert result.parse_status == ParseStatus.FAILED
    assert result.media is None
    assert result.error == "Image could not be decoded. Upload a valid PNG, JPEG, or WEBP image."
    assert str(tmp_path) not in (result.error or "")
    assert not (tmp_path / "cache" / "media").exists()


@pytest.mark.skipif(not (tesseract_available() and ocr_stack_available()),
                    reason="offline Tesseract stack not installed")
def test_tesseract_polish_model_is_installed_offline():
    import pytesseract

    assert "pol" in pytesseract.get_languages(config="")


@pytest.mark.skipif(not (tesseract_available() and ocr_stack_available()),
                    reason="offline Tesseract stack not installed")
def test_polish_ocr_returns_text_without_network(tmp_path):
    font_path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    if not font_path.is_file():
        pytest.skip("DejaVu synthetic test font is not installed")
    path = tmp_path / "synthetic-polish.png"
    image = Image.new("RGB", (900, 130), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(font_path), 42)
    draw.text((12, 24), "Zażółć gęślą jaźń 123", font=font, fill="black")
    image.save(path, format="PNG")

    result = parse_image(path, artifact_id="synthetic-polish-ocr")

    assert result.ocr_engine == "tesseract"
    assert result.error is None
    assert result.media is not None
    assert result.media.ocr_text
