import sqlite3
from fastapi.testclient import TestClient
from backend.api.main import app
from backend.api.live import stable_campaign
from backend.db import Repository
from backend.engine.linking import LinkEdge
from backend.engine.memory import Campaign, classify, cluster_incidents
from backend.pipeline.models import Artifact, Coverage, Evidence, Incident, MediaRef
client = TestClient(app)
def test_live_repository_endpoints_and_safe_media(tmp_path, monkeypatch):
    db = tmp_path / "live.db"
    media_path = tmp_path / "cache" / "frame.png"; media_path.parent.mkdir(); media_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    monkeypatch.setenv("SCAMGRAPH_DB", str(db)); monkeypatch.setenv("SCAMGRAPH_CACHE_DIR", str(media_path.parent))
    repo = Repository(db)
    for identifier in ("inc-a", "inc-b"):
        incident = Incident(identifier, "synthetic", title=f"Masked {identifier}",
            coverage=Coverage(kinds_present=["har"]))
        repo.save_incident(incident)
        artifact = Artifact(f"art-{identifier}", identifier, "har", f"safe/{identifier}.har",
            parse_status="ok", error="/private/raw/source")
        repo.save_artifacts([artifact])
        repo.save_evidence(identifier, [Evidence("pixel_id", "A", None, "hash", "pixel-****",
            artifact_id=artifact.id)])
    repo.save_media([MediaRef("media-a", "art-inc-a", "frame", "sha", path=str(media_path))])
    edge = LinkEdge("inc-a", "inc-b", "campaign", "A", (), 1.0, 2, False, ())
    campaign = Campaign("campaign-inc-a", "campaign", ("inc-a", "inc-b"), (), ())
    network = Campaign("network-inc-a", "network", ("inc-a", "inc-b"), (), ())
    repo.save_analysis([edge], [campaign, network])
    repo.save_run("run-live", "done", "2026-01-01T00:00:00Z", summary={"incidents": 2}, error="/private/raw/source")
    assert "/private" not in client.get("/api/runs/latest").text
    assert len(client.get("/api/incidents").json()) == 2
    detail = client.get("/api/incidents/inc-a").json()
    assert detail["evidence"][0]["display"] == "pixel-****" and detail["campaign_id"] == campaign.id
    assert "/private" not in client.get("/api/artifacts/art-inc-a").text
    assert client.get("/api/campaigns/campaign-inc-a").json()["size"] == 2 and len(client.get("/api/graph").json()["edges"]) == 1
    assert client.get("/api/media/media-a").content.startswith(b"\x89PNG")
    outside = tmp_path / "outside.png"; outside.write_bytes(b"unsafe")
    repo.save_media([MediaRef("media-outside", "art-inc-a", "image", "sha2", path=str(outside))])
    assert client.get("/api/media/media-outside").status_code == 404
def test_live_import_requires_configured_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("SCAMGRAPH_DB", str(tmp_path / "live.db"))
    monkeypatch.delenv("SCAMGRAPH_DATA_DIR", raising=False)
    assert client.get("/api/runs/latest").status_code == 404
    response = client.post("/api/import", json={})
    assert response.status_code == 422 and response.json()["error"] == "validation_error"
    data = tmp_path / "data" / "case"; data.mkdir(parents=True); (data / "note.txt").write_text("synthetic")
    monkeypatch.setenv("SCAMGRAPH_DATA_DIR", str(data.parent)); monkeypatch.setenv("SCAMGRAPH_SALT", "test-salt")
    accepted = client.post("/api/import", json={}); run_id = accepted.json()["run_id"]
    assert accepted.status_code == 202 and client.get(f"/api/runs/{run_id}").json()["status"] == "done"
    repo = Repository(tmp_path / "live.db")
    with sqlite3.connect(repo.path) as db: assert db.execute("SELECT count(*) FROM runs").fetchone()[0] == 1
    assert repo.list_decisions() and client.get("/api/incidents").json()[0]["reason_summary"]
def test_live_classify_and_upload_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("SCAMGRAPH_DB", str(tmp_path / "live.db"))
    monkeypatch.setenv("SCAMGRAPH_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SCAMGRAPH_SALT", "synthetic-test-salt")
    response = client.post("/api/classify", files={"text": (None, "synthetic note")})
    assert response.status_code == 200 and response.json()["outcome"] in {
        "known_campaign", "new_candidate", "needs_review"}
    huge = client.post("/api/classify", files={"files": ("safe.txt", b"x" * 10_000_001)})
    assert huge.status_code == 413 and huge.json()["error"] == "http_error"
def test_held_out_campaign_id_maps_to_full_memory():
    edges = [LinkEdge(a, b, "campaign", "A", (), 1, 2, False, ()) for a, b in (("a", "b"), ("a", "c"), ("b", "c"))]
    full = cluster_incidents(["a", "b", "c"], edges); held = cluster_incidents(["a", "b", "c"], edges, exclude_incident="a")
    result = classify("a", edges[:2], held, coverage_ok=True, exclude_incident="a")
    assert stable_campaign(result, full, "a") == full.campaign_by_incident["a"]
