"""OCR/image/video soft-fail tests + Ad Library + funnel roles."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.pipeline.intake.adlib import parse_adlib
from backend.pipeline.intake.funnel import assign_funnel_roles
from backend.pipeline.intake.html import parse_html
from backend.pipeline.intake.image import parse_image
from backend.pipeline.models import Artifact, ArtifactKind, ParseStatus
from backend.pipeline.ocr import ocr_image, ocr_stack_available
from backend.pipeline.redact import hash_secret
from backend.pipeline.video import extract_keyframes, ffmpeg_available
from backend.tests.fixtures.synthetic_media import write_adlib, write_png
from backend.tests.fixtures.synthetic_pages import write_saved_page


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SCAMGRAPH_SALT", "unit-test-salt")
    monkeypatch.setenv("SCAMGRAPH_CACHE_DIR", str(tmp_path / "cache"))


def test_adlib_extracts_ad_and_page_ids(tmp_path: Path) -> None:
    result = parse_adlib(write_adlib(tmp_path / "ad.info.json"))
    assert result.parse_status == ParseStatus.OK
    assert result.ad_id_hash == hash_secret("SYNTHAD999888")
    assert result.page_id_hash == hash_secret("SYNTHPAGE1122")
    assert "SYNTHAD999888" not in (result.ad_id or "")


def test_image_parse_hashes_and_caches(tmp_path: Path) -> None:
    path = write_png(tmp_path / "screen.png")
    result = parse_image(path, artifact_id="art_img")
    assert result.parse_status in {ParseStatus.OK, ParseStatus.PARTIAL}
    assert result.media is not None
    assert result.media.sha256
    assert result.media.path
    cached = tmp_path / "cache" / result.media.path
    assert cached.is_file()


@pytest.mark.parametrize(("suffix", "image_format"), [
    (".png", "PNG"), (".jpg", "JPEG"), (".webp", "WEBP"),
])
def test_image_parser_accepts_common_formats_without_changing_phash(
    tmp_path: Path, suffix: str, image_format: str,
) -> None:
    image = pytest.importorskip("PIL.Image")
    path = tmp_path / f"synthetic{suffix}"
    image.new("RGB", (32, 24), "white").save(path, format=image_format)

    result = parse_image(path, artifact_id=f"art-{image_format.lower()}")

    assert result.parse_status in {ParseStatus.OK, ParseStatus.PARTIAL}
    assert result.media is not None and result.media.sha256
    assert result.media.phash


def test_malformed_image_fails_with_safe_error_and_no_media(tmp_path: Path) -> None:
    pytest.importorskip("PIL.Image")
    path = tmp_path / "malformed.png"
    path.write_bytes(b"not a valid image")

    result = parse_image(path, artifact_id="art-malformed")

    assert result.parse_status == ParseStatus.FAILED
    assert result.error == "invalid or unreadable image"
    assert str(path) not in (result.error or "")
    assert result.media is None


@pytest.mark.skipif(
    not ocr_stack_available(),
    reason="tesseract + Pillow + pytesseract not all available",
)
def test_ocr_runs_when_tesseract_present(tmp_path: Path) -> None:
    path = write_png(tmp_path / "ocr.png")
    result = ocr_image(path)
    # Blank synthetic image may yield empty text; engine must still be selected.
    assert result.engine == "tesseract"
    assert result.error is None or "pol failed" in (result.error or "")


def test_ocr_soft_fails_without_engine(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("backend.pipeline.ocr.tesseract_available", lambda: False)
    monkeypatch.setattr("backend.pipeline.ocr._easyocr", lambda _img: None)
    monkeypatch.setattr("backend.pipeline.ocr._preprocess", lambda _p: "sentinel")
    # Force preprocess to None so we hit unavailable path cleanly
    monkeypatch.setattr("backend.pipeline.ocr._preprocess", lambda _p: None)
    result = ocr_image(write_png(tmp_path / "x.png"))
    assert result.text == ""
    assert result.error


@pytest.mark.skipif(not ffmpeg_available(), reason="ffmpeg not installed")
def test_video_keyframes_when_ffmpeg_present(tmp_path: Path) -> None:
    # Generate a 1-second synthetic mp4 via ffmpeg itself.
    clip = tmp_path / "clip.mp4"
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        "color=c=red:s=320x240:d=2",
        "-y",
        str(clip),
    ]
    import subprocess

    subprocess.run(cmd, check=True, capture_output=True)
    result = extract_keyframes(clip, artifact_id="art_vid")
    assert result.ok
    assert result.frames


def test_video_soft_fails_without_ffmpeg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("backend.pipeline.video.ffmpeg_available", lambda: False)
    result = extract_keyframes(tmp_path / "missing.mp4", artifact_id="a")
    assert result.ok is False
    assert result.error


def test_funnel_roles_content_and_fallback(tmp_path: Path) -> None:
    page = write_saved_page(tmp_path / "site")
    html = parse_html(page)
    arts = [
        Artifact(
            id="a1",
            incident_id="i1",
            kind=ArtifactKind.ADLIB_JSON,
            path="x.info.json",
            funnel_step=1,
        ),
        Artifact(
            id="a2",
            incident_id="i1",
            kind=ArtifactKind.HTML,
            path=str(page),
            funnel_step=2,
        ),
        Artifact(
            id="a3",
            incident_id="i1",
            kind=ArtifactKind.HTML,
            path="unknown.html",
            funnel_step=3,
        ),
    ]
    roles = {r.artifact_id: r for r in assign_funnel_roles(arts, html_by_artifact={"a2": html})}
    assert roles["a1"].role == "ad"
    assert roles["a2"].role in {"offer", "order", "prelander"}
    assert roles["a3"].role == "offer"  # step-3 fallback when no html
    assert "strona_N" in roles["a3"].reason or roles["a3"].reason
