from fastapi.testclient import TestClient

from backend.api.main import app
from backend.db import Repository
from backend.pipeline.models import Artifact, ArtifactKind, Coverage, Incident, MediaRef, ParseStatus

client = TestClient(app)


def test_valid_image_artifact_detail_has_no_parse_error(tmp_path, monkeypatch):
    db_path = tmp_path / "valid-image-detail.db"
    monkeypatch.setenv("SCAMGRAPH_DB", str(db_path))
    repo = Repository(db_path)
    repo.save_incident(Incident("synthetic-valid-image-case", "synthetic", coverage=Coverage()))
    repo.save_artifacts([Artifact(
        id="synthetic-valid-image-artifact", incident_id="synthetic-valid-image-case",
        kind=ArtifactKind.IMAGE, path="media/synthetic.png", parser="image",
        parse_status=ParseStatus.OK,
    )])

    response = client.get("/api/artifacts/synthetic-valid-image-artifact")

    assert response.status_code == 200
    assert response.json()["parse_status"] == "ok"
    assert response.json()["error"] is None


def test_artifact_detail_returns_saved_ocr_and_safe_partial_image_message(tmp_path, monkeypatch):
    db_path = tmp_path / "image-detail.db"
    monkeypatch.setenv("SCAMGRAPH_DB", str(db_path))
    repo = Repository(db_path)
    repo.save_incident(Incident("synthetic-image-case", "synthetic", coverage=Coverage()))
    repo.save_artifacts([Artifact(
        id="synthetic-webp-artifact", incident_id="synthetic-image-case",
        kind=ArtifactKind.IMAGE, path="/private/test/input.webp",
        parser="image", parse_status=ParseStatus.PARTIAL,
        error="no OCR engine available (install tesseract-ocr-pol or easyocr)",
    )])
    repo.save_media([MediaRef(
        id="synthetic-webp-media", artifact_id="synthetic-webp-artifact", kind="image",
        sha256="synthetic-digest", path="media/synthetic.webp", phash="0123456789abcdef",
        ocr_text="synthetic Polish advert text",
    )])

    response = client.get("/api/artifacts/synthetic-webp-artifact")

    assert response.status_code == 200
    body = response.json()
    assert body["parse_status"] == "partial"
    assert body["error"] == "Image saved, but Polish OCR is unavailable. Install Tesseract with Polish language data."
    assert body["media"][0]["ocr_text"] == "synthetic Polish advert text"
    assert "/private/test" not in response.text
    assert "no OCR engine available" not in response.text


def test_image_and_non_image_parse_errors_are_safe_and_specific(tmp_path, monkeypatch):
    db_path = tmp_path / "parse-errors.db"
    monkeypatch.setenv("SCAMGRAPH_DB", str(db_path))
    repo = Repository(db_path)
    repo.save_incident(Incident("synthetic-error-case", "synthetic", coverage=Coverage()))
    repo.save_artifacts([
        Artifact(id="synthetic-malformed-image", incident_id="synthetic-error-case",
                 kind=ArtifactKind.IMAGE, path="/private/secrets/ad.webp", parser="image",
                 parse_status=ParseStatus.FAILED,
                 error="UnidentifiedImageError: cannot identify image file '/private/secrets/ad.webp'"),
        Artifact(id="synthetic-failed-html", incident_id="synthetic-error-case",
                 kind=ArtifactKind.HTML, path="/private/secrets/page.html", parser="html",
                 parse_status=ParseStatus.FAILED,
                 error="OSError: failed reading /private/secrets/page.html"),
    ])

    malformed = client.get("/api/artifacts/synthetic-malformed-image")
    html = client.get("/api/artifacts/synthetic-failed-html")

    assert malformed.status_code == html.status_code == 200
    assert malformed.json()["error"] == "Image could not be decoded. Upload a valid PNG, JPEG, or WEBP image."
    assert html.json()["error"] == "Parse failed"
    assert "/private/secrets" not in malformed.text + html.text
    assert "UnidentifiedImageError" not in malformed.text
