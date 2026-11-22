import json
import sqlite3

from fastapi.testclient import TestClient

from backend.api import live
from backend.api.main import app
from backend.db import Repository
from backend.engine.linking import LinkEdge
from backend.engine.memory import Campaign
from backend.pipeline.models import Coverage, Incident, IncidentBundle
from backend.tests.fixtures.synthetic_media import write_adlib, write_png

client = TestClient(app)


def test_reanalysis_preserves_manual_edge_and_campaign_overrides(tmp_path):
    repo = Repository(tmp_path / "overrides.db")
    for incident_id in ("inc-a", "inc-b", "inc-c", "inc-d"):
        repo.save_incident(Incident(incident_id, "synthetic", coverage=Coverage()))
    campaigns = [
        Campaign("camp-a", "campaign", ("inc-a", "inc-b"), (), ()),
        Campaign("camp-b", "campaign", ("inc-c", "inc-d"), (), ()),
    ]
    edge = LinkEdge("inc-a", "inc-b", "campaign", "A", (), 1.0, 1, False, ())
    repo.save_analysis([edge], campaigns)
    assert repo.record_edge_decision("edge-inc-a-inc-b", "confirm")
    repo.merge_campaigns(["camp-a", "camp-b"])
    _, split_id = repo.split_campaign("camp-a", ["inc-b", "inc-c"])

    # A new upload rebuilds these same derived tables; analyst actions must survive.
    repo.save_analysis([edge], campaigns)

    assert {row["id"]: row["status"] for row in repo.list_edges()}["edge-inc-a-inc-b"] == "confirmed"
    memberships = {(row["campaign_id"], row["incident_id"]) for row in repo.list_membership()}
    assert memberships == {
        ("camp-a", "inc-a"), ("camp-a", "inc-d"),
        (split_id, "inc-b"), (split_id, "inc-c"),
    }
    assert "camp-b" not in {row["id"] for row in repo.list_campaigns()}


def test_reanalysis_preserves_direct_campaign_split(tmp_path):
    repo = Repository(tmp_path / "direct-split.db")
    for incident_id in ("inc-a", "inc-b", "inc-c"):
        repo.save_incident(Incident(incident_id, "synthetic", coverage=Coverage()))
    campaign = Campaign("camp-direct", "campaign", ("inc-a", "inc-b", "inc-c"), (), ())
    repo.save_analysis([], [campaign])
    _, split_id = repo.split_campaign("camp-direct", ["inc-b"])

    # Even if the derived campaign disappears or changes ID, both analyst groups survive.
    repo.save_analysis([], [Campaign("reclustered", "campaign", ("inc-a", "inc-b", "inc-c"), (), ())])

    memberships = {(row["campaign_id"], row["incident_id"]) for row in repo.list_membership()}
    assert memberships == {
        ("camp-direct", "inc-a"), ("camp-direct", "inc-c"), (split_id, "inc-b"),
    }


def test_rejected_edge_is_not_used_for_reanalysis_memory(tmp_path, monkeypatch):
    repo = Repository(tmp_path / "rejected-edge.db")
    repo.save_incident(Incident("inc-a", "synthetic", coverage=Coverage()))
    repo.save_incident(Incident("inc-b", "synthetic", coverage=Coverage()))
    edge = LinkEdge("inc-a", "inc-b", "campaign", "A", (), 1.0, 1, False, ())
    monkeypatch.setattr(live, "link_incidents", lambda _grouped: [edge])
    repo.save_analysis([edge], [Campaign("camp-a", "campaign", ("inc-a", "inc-b"), (), ())])
    assert repo.record_edge_decision("edge-inc-a-inc-b", "reject")

    edges, campaigns, decisions, _ = live.analysis_snapshot(repo)

    assert len(edges) == 1  # Keep the rejected link visible for analyst review.
    assert campaigns == []
    assert all(row["campaign_id"] is None for row in decisions)


def test_next_upload_classification_ignores_rejected_memory_edge(tmp_path, monkeypatch):
    repo = Repository(tmp_path / "next-upload.db")
    repo.save_incident(Incident("inc-a", "synthetic", coverage=Coverage()))
    repo.save_incident(Incident("inc-b", "synthetic", coverage=Coverage()))
    rejected = LinkEdge("inc-a", "inc-b", "campaign", "A", (), 1.0, 1, False, ())
    repo.save_analysis([rejected], [])
    assert repo.record_edge_decision("edge-inc-a-inc-b", "reject")
    monkeypatch.setattr(live, "process_input", lambda *_args: IncidentBundle(
        Incident("temporary", "synthetic", coverage=Coverage())
    ))
    observed_memory_edges = []
    original_cluster = live.cluster_incidents

    def track_memory(grouped, edges, **kwargs):
        observed_memory_edges.extend((edge.source, edge.target) for edge in edges)
        return original_cluster(grouped, edges, **kwargs)

    monkeypatch.setattr(live, "cluster_incidents", track_memory)
    monkeypatch.setattr(live, "link_incidents", lambda grouped: [
        rejected,
        LinkEdge("inc-a", next(key for key in grouped if key.startswith("inc_")),
                 "campaign", "A", (), 1.0, 1, False, ()),
    ])
    boundary = "synthetic-boundary"
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"text\"\r\n\r\n"+
            f"sample\r\n--{boundary}--\r\n").encode()

    _, _, candidate = live.classify_multipart(repo, body, f"multipart/form-data; boundary={boundary}")

    assert observed_memory_edges == []
    assert candidate and all(edge.source != "inc-b" for edge in candidate)


def _upload_ad(content: bytes):
    return client.post("/api/classify", files={
        "files": ("synthetic.info.json", content, "application/json"),
    })


def test_upload_is_saved_and_next_upload_uses_it_as_memory(tmp_path, monkeypatch):
    db_path = tmp_path / "live.db"
    monkeypatch.setenv("SCAMGRAPH_DB", str(db_path))
    monkeypatch.setenv("SCAMGRAPH_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SCAMGRAPH_SALT", "synthetic-upload-salt")
    repo = Repository(db_path)
    for index in range(6):
        repo.save_incident(Incident(f"synthetic-background-{index}", "synthetic",
                                    coverage=Coverage()))
    ad_path = write_adlib(tmp_path / "ad.info.json")
    content = ad_path.read_bytes()

    first = _upload_ad(content)
    assert first.status_code == 200
    assert first.json()["outcome"] in {"known_campaign", "new_candidate", "needs_review"}
    assert "SYNTHAD999888" not in first.text

    stored = [item for item in repo.list_incidents() if item["title"] == "Uploaded material"]
    assert len(stored) == 1
    first_id = stored[0]["id"]
    artifacts = repo.get_artifacts(first_id)
    assert len(artifacts) == 1
    assert len(repo.get_evidence(first_id)) == 2
    assert first_id in {row["id"] for row in client.get("/api/incidents").json()}
    assert (tmp_path / "cache" / "classify").is_dir()
    with sqlite3.connect(db_path) as db:
        action, subject_id, details = db.execute(
            "SELECT action,subject_id,detail_json FROM audit_log ORDER BY id"
        ).fetchone()
    assert action == "incident.upload" and subject_id == first_id
    assert json.loads(details)["artifact_count"] == 1
    assert "SYNTHAD999888" not in details

    second = _upload_ad(content)
    assert second.status_code == 200
    assert len([item for item in repo.list_incidents() if item["title"] == "Uploaded material"]) == 2
    assert repo.list_decisions()
    assert repo.list_campaigns()
    assert any(edge["status"] == "active" for edge in repo.list_edges())
    assert second.json()["candidate_edges"]


def test_uploaded_image_media_is_stored_and_served_from_app_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("SCAMGRAPH_DB", str(tmp_path / "live.db"))
    monkeypatch.setenv("SCAMGRAPH_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SCAMGRAPH_SALT", "synthetic-upload-salt")
    png_path = write_png(tmp_path / "synthetic.png")

    response = client.post("/api/classify", files={
        "files": ("synthetic.png", png_path.read_bytes(), "image/png"),
    })
    assert response.status_code == 200
    repo = Repository(tmp_path / "live.db")
    incident = repo.list_incidents()[0]
    artifact = repo.get_artifacts(incident["id"])[0]
    media = repo.list_media(artifact["id"])
    assert len(media) == 1
    assert client.get(f"/api/media/{media[0]['id']}").content.startswith(b"\x89PNG")


def test_leave_one_out_upload_does_not_add_a_second_incident(tmp_path, monkeypatch):
    monkeypatch.setenv("SCAMGRAPH_DB", str(tmp_path / "live.db"))
    monkeypatch.setenv("SCAMGRAPH_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SCAMGRAPH_SALT", "synthetic-upload-salt")
    content = write_adlib(tmp_path / "ad.info.json").read_bytes()
    assert _upload_ad(content).status_code == 200
    repo = Repository(tmp_path / "live.db")
    assert len(repo.list_incidents()) == 1

    response = client.post("/api/classify", files={
        "files": ("synthetic.info.json", content, "application/json"),
        "exclude_incident": (None, repo.list_incidents()[0]["id"]),
    })
    assert response.status_code == 200
    assert len(repo.list_incidents()) == 1


def test_upload_save_failure_returns_safe_error_without_partial_rows(tmp_path, monkeypatch):
    db_path = tmp_path / "live.db"
    monkeypatch.setenv("SCAMGRAPH_DB", str(db_path))
    monkeypatch.setenv("SCAMGRAPH_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SCAMGRAPH_SALT", "synthetic-upload-salt")

    def fail_analysis(db, *_args, **_kwargs):
        db.execute("INSERT INTO edges VALUES (?,?,?,?,?,?,?,?)",
            ("synthetic-edge", "missing-a", "missing-b", "campaign", 1.0, 1, "[]", "active"))

    monkeypatch.setattr(Repository, "_replace_analysis", staticmethod(fail_analysis))
    png_path = write_png(tmp_path / "synthetic.png")
    response = client.post("/api/classify", files={
        "files": ("synthetic.png", png_path.read_bytes(), "image/png"),
    })
    assert response.status_code == 500
    assert response.json()["detail"] == "Uploaded material could not be saved for future analysis"
    assert Repository(db_path).list_incidents() == []
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT count(*) FROM artifacts").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM audit_log").fetchone()[0] == 0
    assert not list((tmp_path / "cache" / "classify").glob("batch_*"))
    assert not list((tmp_path / "cache" / "media").glob("*"))
