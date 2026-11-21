from fastapi.testclient import TestClient

from backend.api.main import app
from backend.db import Repository
from backend.engine.linking import LinkEdge
from backend.engine.memory import Campaign
from backend.pipeline.models import Artifact, Coverage, Evidence, Incident, MediaRef

client = TestClient(app)


def test_live_repository_endpoints_and_safe_media(tmp_path, monkeypatch):
    db = tmp_path / "live.db"
    media_path = tmp_path / "cache" / "frame.png"
    media_path.parent.mkdir()
    media_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    monkeypatch.setenv("SCAMGRAPH_DB", str(db))
    monkeypatch.setenv("SCAMGRAPH_CACHE_DIR", str(media_path.parent))
    repo = Repository(db)
    for identifier in ("inc-a", "inc-b"):
        incident = Incident(identifier, "synthetic", title=f"Masked {identifier}",
            coverage=Coverage(kinds_present=["har"]))
        repo.save_incident(incident)
        artifact = Artifact(f"art-{identifier}", identifier, "har", f"safe/{identifier}.har",
            parse_status="ok")
        repo.save_artifacts([artifact])
        repo.save_evidence(identifier, [Evidence("pixel_id", "A", None, "hash", "pixel-****",
            artifact_id=artifact.id)])
    repo.save_media([MediaRef("media-a", "art-inc-a", "frame", "sha", path=str(media_path))])
    edge = LinkEdge("inc-a", "inc-b", "campaign", "A", (), 1.0, 2, False, ())
    campaign = Campaign("campaign-inc-a", "campaign", ("inc-a", "inc-b"), (), ())
    repo.save_analysis([edge], [campaign])
    repo.save_run("run-live", "done", "2026-01-01T00:00:00Z", summary={"incidents": 2})

    assert client.get("/api/runs/latest").json()["id"] == "run-live"
    assert len(client.get("/api/incidents").json()) == 2
    assert client.get("/api/incidents/inc-a").json()["evidence"][0]["display"] == "pixel-****"
    assert client.get("/api/artifacts/art-inc-a").status_code == 200
    assert client.get("/api/campaigns/campaign-inc-a").json()["size"] == 2
    assert len(client.get("/api/graph").json()["edges"]) == 1
    assert client.get("/api/media/media-a").content.startswith(b"\x89PNG")


def test_live_import_requires_configured_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("SCAMGRAPH_DB", str(tmp_path / "live.db"))
    monkeypatch.delenv("SCAMGRAPH_DATA_DIR", raising=False)
    response = client.post("/api/import", json={})
    assert response.status_code == 422 and response.json()["error"] == "validation_error"


def test_live_classify_and_upload_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("SCAMGRAPH_DB", str(tmp_path / "live.db"))
    monkeypatch.setenv("SCAMGRAPH_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SCAMGRAPH_SALT", "synthetic-test-salt")
    response = client.post("/api/classify", files={"text": (None, "synthetic note")})
    assert response.status_code == 200 and response.json()["outcome"] in {
        "known_campaign", "new_candidate", "needs_review"}
    huge = client.post("/api/classify", files={"files": ("safe.txt", b"x" * 10_000_001)})
    assert huge.status_code == 413 and huge.json()["error"] == "http_error"
