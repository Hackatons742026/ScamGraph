import csv
import io
import json
import sqlite3
from fastapi.testclient import TestClient
from backend.api.main import app
from backend.api.live import stable_campaign
from backend.db import Repository
from backend.exports.formats import render_csv, render_html
from backend.engine.linking import LinkEdge, MatchedEvidence
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
    assert detail["ingested_at"] and detail["first_seen"] is None
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
    assert response.json()["elapsed_ms"] >= 1
    huge = client.post("/api/classify", files={"files": ("safe.txt", b"x" * 10_000_001)})
    assert huge.status_code == 413 and huge.json()["error"] == "http_error"


def test_demo_classification_duration_uses_monotonic_measurement(monkeypatch):
    from backend.api import routes

    monkeypatch.delenv("SCAMGRAPH_DB", raising=False)
    ticks = iter((10.0, 10.1041))
    monkeypatch.setattr(routes, "perf_counter", lambda: next(ticks))
    response = client.post("/api/classify", files={"text": (None, "synthetic note")})
    assert response.status_code == 200
    assert response.json()["elapsed_ms"] == 105

def test_live_campaign_graph_and_coverage_are_ui_friendly(tmp_path, monkeypatch):
    monkeypatch.setenv("SCAMGRAPH_DB", str(tmp_path / "quality.db"))
    repo = Repository(tmp_path / "quality.db")
    dates = {
        "inc-a": ("2026-01-02T00:00:00+00:00", "2026-01-03T00:00:00+00:00"),
        "inc-b": ("2026-01-01T00:00:00+00:00", "2026-01-04T00:00:00+00:00"),
        "inc-c": ("2026-01-05T00:00:00+00:00", "2026-01-05T00:00:00+00:00"),
        "inc-unassigned": (None, None),
    }
    for identifier, (first_seen, last_seen) in dates.items():
        coverage = Coverage(kinds_present=["video"], kinds_missing=["har", "html"],
                            notes=["no HAR", "video only", "evidence_types=1"])
        folder_title = {
            "inc-a": "Folder Alpha",
            "inc-b": "Folder Beta",
            "inc-c": "Folder Gamma",
            "inc-unassigned": "Folder Delta",
        }[identifier]
        repo.save_incident(Incident(identifier, "PRIVATE_FOLDER", title=folder_title,
            first_seen=first_seen, last_seen=last_seen, coverage=coverage))
    for identifier in ("inc-a", "inc-b"):
        artifact = Artifact(f"art-{identifier}", identifier, "har", "private/path.har",
                            parse_status="ok")
        repo.save_artifacts([artifact])
        evidence_rows = [Evidence("pixel_id", "A", None, "shared-hash",
            "pixel-****12", weight=3.0, artifact_id=artifact.id, funnel_step=1)]
        if identifier == "inc-a":
            evidence_rows.append(Evidence("click_domain", "B", "tds", "secondary-hash",
                "go.****.test", weight=99.0, artifact_id=artifact.id, funnel_step=1))
        repo.save_evidence(identifier, evidence_rows)
    matched = MatchedEvidence("pixel_id", "A", None, "pixel-****12", "shared-hash", 3.0,
                              ("art-inc-a", "art-inc-b"), (1,), "exact hash match")
    edge = LinkEdge("inc-a", "inc-b", "campaign", "A", (), 3.0, 1, False, (matched,))
    repo.save_analysis([edge], [
        Campaign("campaign-x", "campaign", ("inc-a", "inc-b"), ("pixel_id",), ()),
        Campaign("network-x", "network", ("inc-a", "inc-b", "inc-c"), ("pixel_id",), ()),
    ])

    incidents = {item["id"]: item for item in client.get("/api/incidents").json()}
    assert incidents["inc-a"]["label"] == "Folder Alpha"
    assert incidents["inc-b"]["label"] == "Folder Beta"
    assert len({item["label"] for item in incidents.values()}) == len(incidents)
    assert "PRIVATE" not in incidents["inc-a"]["label"]
    assert "private/path" not in json.dumps(incidents["inc-a"])
    assert incidents["inc-a"]["campaign_label"] == "Campaign 1"
    assert incidents["inc-a"]["network_id"] == "network-x"
    assert incidents["inc-c"]["campaign_id"] is None
    assert incidents["inc-c"]["network_id"] == "network-x"
    assert incidents["inc-c"]["coverage"]["badges"] == ["no HAR", "no HTML", "video only"]

    campaigns = {item["id"]: item for item in client.get("/api/campaigns").json()}
    campaign = campaigns["campaign-x"]
    assert campaign["label"] == "Campaign 1" and campaign["network_id"] == "network-x"
    assert campaign["membership_source"] == "automatic"
    assert campaign["first_seen"] == dates["inc-b"][0]
    assert campaign["last_seen"] == dates["inc-b"][1]
    assert campaign["strongest_evidence"]["type"] == "pixel_id"
    assert campaign["strongest_evidence"]["display"] == "pixel-****12"
    network = campaigns["network-x"]
    assert network["label"] == "Network 1"
    assert network["first_seen"] == dates["inc-b"][0]
    assert network["last_seen"] == dates["inc-c"][1]
    assert network["strongest_evidence"]["type"] == "pixel_id"

    graph = client.get("/api/graph").json()
    nodes = {node["id"]: node for node in graph["nodes"]}
    assert {"campaign", "network", "unassigned"} <= {node["kind"] for node in graph["nodes"]}
    assert nodes["campaign-x"]["label"] == "Campaign 1"
    assert nodes["campaign-x"]["parent"] == "network-x"
    assert nodes["inc-a"]["parent"] == "campaign-x"
    assert nodes["inc-c"]["parent"] == "network-x"
    assert nodes["inc-unassigned"]["parent"] == "unassigned"
    assert graph["edges"][0]["evidence"][0]["display"] == "pixel-****12"

    network_graph = client.get("/api/graph", params={"campaign": "network-x"}).json()
    network_ids = {node["id"] for node in network_graph["nodes"]}
    assert {"inc-a", "inc-b", "inc-c", "campaign-x", "network-x"} <= network_ids
    assert "inc-unassigned" not in network_ids


def test_uploaded_incident_labels_are_unique_and_keep_source_times_unknown(tmp_path, monkeypatch):
    monkeypatch.setenv("SCAMGRAPH_DB", str(tmp_path / "uploads.db"))
    repo = Repository(tmp_path / "uploads.db")
    for identifier in ("upload-abc123", "upload-def456"):
        repo.save_incident(Incident(identifier, "synthetic", title="Uploaded material"))

    rows = {row["id"]: row for row in client.get("/api/incidents").json()}
    assert rows["upload-abc123"]["label"] == "Upload abc123"
    assert rows["upload-def456"]["label"] == "Upload def456"
    assert rows["upload-abc123"]["first_seen"] is None
    assert rows["upload-abc123"]["last_seen"] is None
    assert rows["upload-abc123"]["ingested_at"]
    assert rows["upload-def456"]["ingested_at"]

def test_campaign_exports_are_masked_downloads(tmp_path, monkeypatch):
    monkeypatch.setenv("SCAMGRAPH_DB", str(tmp_path / "export.db"))
    monkeypatch.setenv("SCAMGRAPH_SALT", "synthetic-export-salt")
    repo = Repository(tmp_path / "export.db")
    raw_display = "RAW_PRIVATE_SENTINEL"
    raw_path = "/local/private/SYNTHETIC_SOURCE_SENTINEL.har"
    for identifier in ("inc-export-a", "inc-export-b"):
        repo.save_incident(Incident(identifier, raw_path, title="PRIVATE_TITLE_SENTINEL",
            coverage=Coverage(kinds_present=["har"])))
        artifact = Artifact(f"art-{identifier}", identifier, "har", raw_path,
            role="prelander", parse_status="ok")
        repo.save_artifacts([artifact])
        repo.save_evidence(identifier, [Evidence("landing_domain", "B", "domain",
            "synthetic-private-hash", raw_display, artifact_id=artifact.id, funnel_step=1)])
    campaign = Campaign("campaign-export-a", "campaign", ("inc-export-a", "inc-export-b"), (), ())
    repo.save_analysis([], [campaign])

    urls = {
        "html": ("/api/exports/campaign-export-a.html", "text/html"),
        "csv": ("/api/exports/campaign-export-a.csv", "text/csv"),
        "misp": ("/api/exports/campaign-export-a.misp.json", "application/json"),
    }
    responses = {kind: client.get(url) for kind, (url, _) in urls.items()}
    for kind, (url, media_type) in urls.items():
        response = responses[kind]
        assert response.status_code == 200
        assert response.headers["content-type"].startswith(media_type)
        assert "attachment; filename=" in response.headers["content-disposition"]
        assert response.headers["cache-control"] == "no-store"
        for private in (raw_display, raw_path, "PRIVATE_TITLE_SENTINEL", "synthetic-private-hash",
                        "campaign-export-a", "inc-export-a", "inc-export-b", "art-inc-export-a"):
            assert private not in response.text
        assert "campaign-export-a" not in response.headers["content-disposition"]

    rows = list(csv.DictReader(io.StringIO(responses["csv"].text)))
    evidence_rows = [row for row in rows if row["record_type"] == "evidence"]
    assert evidence_rows and evidence_rows[0]["masked_ref"].startswith("value-")
    assert evidence_rows[0]["artifact_kind"] == "har" and evidence_rows[0]["funnel_step"] == "1"
    assert {row["record_type"] for row in rows} >= {"incident", "artifact", "evidence"}
    event = json.loads(responses["misp"].text)["Event"]
    assert event["info"].startswith("ScamGraph masked campaign campaign-")
    assert {"Orgc", "analysis", "timestamp", "threat_level_id", "Attribute"} <= set(event)
    assert "date" not in event  # No source timestamp was supplied.
    assert event["Orgc"]["uuid"] and event["Attribute"][0]["uuid"]
    assert event["Attribute"] and event["Attribute"][0]["to_ids"] is False
    assert "event_uuid" not in event["Attribute"][0]
    assert event["Attribute"][0]["value"].startswith("masked:landing_domain:value-")
    assert client.get("/api/exports/missing.csv").status_code == 404
    assert client.get("/api/exports/network-export-a.csv").status_code == 404
    assert client.get("/api/exports/campaign-export-a.xml").status_code == 404

def test_csv_export_neutralizes_spreadsheet_formulas():
    data = {
        "campaign_ref": "campaign-safe", "incidents": [{"ref": "incident-safe",
            "first_seen": " =2+2", "last_seen": ""}],
        "artifacts": [{"ref": "artifact-safe", "incident_ref": "incident-safe",
            "kind": "@SUM(1,2)", "funnel_step": None}],
        "evidence": [{"incident_ref": "incident-safe", "artifact_ref": "artifact-safe",
            "artifact_kind": None, "type": "-2+3", "tier": "\t=4+5", "family": "+6+7",
            "masked_ref": "value-safe", "funnel_step": None}],
        "edges": [],
    }
    rows = list(csv.DictReader(io.StringIO(render_csv(data).decode("utf-8"))))
    incident = next(row for row in rows if row["record_type"] == "incident")
    artifact = next(row for row in rows if row["record_type"] == "artifact")
    evidence = next(row for row in rows if row["record_type"] == "evidence")
    assert incident["first_seen"] == "' =2+2"
    assert artifact["artifact_kind"] == "'@SUM(1,2)"
    assert evidence["evidence_type"] == "'-2+3"
    assert evidence["tier"] == "'\t=4+5"
    assert evidence["family"] == "'+6+7"


def test_misp_export_uses_only_source_date_and_omits_unknown_date():
    from backend.exports.formats import render_misp

    base = {"campaign_ref": "campaign-safe", "generated_at": "2026-11-22T12:00:00+00:00",
        "date": None, "evidence": [], "incidents": [], "artifacts": [], "edges": []}
    event = json.loads(render_misp(base))["Event"]
    assert "date" not in event
    event = json.loads(render_misp({**base, "date": "2026-01-01"}))["Event"]
    assert event["date"] == "2026-01-01"


def test_misp_event_date_is_derived_from_source_time_in_utc(tmp_path, monkeypatch):
    monkeypatch.setenv("SCAMGRAPH_DB", str(tmp_path / "misp-date.db"))
    monkeypatch.setenv("SCAMGRAPH_SALT", "synthetic-misp-date-salt")
    repo = Repository(tmp_path / "misp-date.db")
    repo.save_incident(Incident("inc-misp-date", "synthetic",
        first_seen="2026-01-02T00:30:00+02:00"))
    repo.save_analysis([], [Campaign("camp-misp-date", "campaign", ("inc-misp-date",), (), ())])

    response = client.get("/api/exports/camp-misp-date.misp.json")
    assert response.status_code == 200
    assert json.loads(response.text)["Event"]["date"] == "2026-01-01"

def test_html_export_escapes_projection_values():
    data = {"campaign_ref": "campaign-safe", "generated_at": "<script>alert(1)</script>",
        "incidents": [{"ref": "incident-safe", "first_seen": "<img src=x>", "last_seen": ""}],
        "artifacts": [], "evidence": [], "edges": [],
    }
    rendered = render_html(data).decode("utf-8")
    assert "<script>alert(1)</script>" not in rendered
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered
    assert "&lt;img src=x&gt;" in rendered
def test_held_out_campaign_id_maps_to_full_memory():
    edges = [LinkEdge(a, b, "campaign", "A", (), 1, 2, False, ()) for a, b in (("a", "b"), ("a", "c"), ("b", "c"))]
    full = cluster_incidents(["a", "b", "c"], edges); held = cluster_incidents(["a", "b", "c"], edges, exclude_incident="a")
    result = classify("a", edges[:2], held, coverage_ok=True, exclude_incident="a")
    assert stable_campaign(result, full, "a") == full.campaign_by_incident["a"]
