import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.db import Repository
from backend.engine.linking import LinkEdge
from backend.engine.memory import Campaign
from backend.pipeline.models import Coverage, Incident

client = TestClient(app)


@pytest.fixture
def live_overrides(tmp_path, monkeypatch):
    db_path = tmp_path / "overrides.db"
    monkeypatch.setenv("SCAMGRAPH_DB", str(db_path))
    repo = Repository(db_path)
    incident_ids = ("inc-a", "inc-b", "inc-c", "inc-d")
    for identifier in incident_ids:
        repo.save_incident(Incident(identifier, "synthetic", coverage=Coverage(kinds_present=["har"])))

    edges = [
        LinkEdge("inc-a", "inc-b", "campaign", "A", (), 1.0, 2, False, ()),
        LinkEdge("inc-c", "inc-d", "campaign", "B", (), 0.8, 2, False, ()),
    ]
    campaigns = [
        Campaign("camp-a", "campaign", ("inc-a", "inc-b"), (), ()),
        Campaign("camp-b", "campaign", ("inc-c", "inc-d"), (), ()),
        Campaign("network-a", "network", incident_ids, (), ()),
    ]
    decisions = [
        {"incident_id": incident_id, "outcome": "known_campaign",
         "campaign_id": "camp-a" if incident_id in {"inc-a", "inc-b"} else "camp-b",
         "reasons": [], "decided_at": "2026-01-01T00:00:00+00:00"}
        for incident_id in incident_ids
    ]
    repo.save_analysis(edges, campaigns, decisions)
    return repo


def test_edge_confirm_and_reject_are_persisted_and_rejection_hides_link(live_overrides):
    confirmed = client.post("/api/edges/edge-inc-a-inc-b/decision", json={"decision": "confirm", "note": "synthetic note"})
    assert confirmed.status_code == 200
    assert confirmed.json()["edge_id"] == "edge-inc-a-inc-b"
    assert confirmed.json()["decision"] == "confirm" and confirmed.json()["recorded_at"]

    rejected = client.post("/api/edges/edge-inc-c-inc-d/decision", json={"decision": "reject"})
    assert rejected.status_code == 200 and rejected.json()["decision"] == "reject"
    assert [edge["id"] for edge in client.get("/api/graph").json()["edges"]] == ["edge-inc-a-inc-b"]
    assert client.get("/api/incidents/inc-c").json()["edges"] == []

    rows = {row["id"]: row for row in live_overrides.list_edges()}
    assert rows["edge-inc-a-inc-b"]["status"] == "confirmed"
    assert rows["edge-inc-c-inc-d"]["status"] == "rejected"
    with sqlite3.connect(live_overrides.path) as db:
        audit = db.execute("SELECT action,detail_json FROM audit_log ORDER BY id").fetchall()
    assert [row[0] for row in audit] == ["edge.confirm", "edge.reject"]
    assert json.loads(audit[0][1])["note"] == "synthetic note"


def test_campaign_merge_and_split_change_persisted_memberships(live_overrides):
    merged = client.post("/api/campaigns/merge", json={"campaign_ids": ["camp-a", "camp-b"], "note": "synthetic merge"})
    assert merged.status_code == 200
    assert merged.json()["id"] == "camp-a"
    assert {member["id"] for member in merged.json()["members"]} == {"inc-a", "inc-b", "inc-c", "inc-d"}
    assert client.get("/api/campaigns/camp-b").status_code == 404
    assert {row["incident_id"] for row in live_overrides.list_membership() if row["campaign_id"] == "camp-a"} == {
        "inc-a", "inc-b", "inc-c", "inc-d"
    }
    assert {row["campaign_id"] for row in live_overrides.list_decisions()} == {"camp-a"}

    split = client.post("/api/campaigns/split", json={
        "campaign_id": "camp-a", "incident_ids": ["inc-b", "inc-c"], "note": "synthetic split"
    })
    assert split.status_code == 200 and len(split.json()) == 2
    original, separated = split.json()
    assert original["id"] == "camp-a" and {row["id"] for row in original["members"]} == {"inc-a", "inc-d"}
    assert separated["id"].startswith("campaign-override-")
    assert {row["id"] for row in separated["members"]} == {"inc-b", "inc-c"}
    assert {row["campaign_id"] for row in live_overrides.list_decisions()} == {"camp-a", separated["id"]}
    with sqlite3.connect(live_overrides.path) as db:
        actions = [row[0] for row in db.execute("SELECT action FROM audit_log ORDER BY id")]
    assert actions == ["campaign.merge", "campaign.split"]


def test_overrides_reject_unknown_ids_and_invalid_subsets(live_overrides):
    assert client.post("/api/edges/missing/decision", json={"decision": "confirm"}).status_code == 404
    assert client.post("/api/campaigns/merge", json={"campaign_ids": ["camp-a", "missing"]}).status_code == 404
    assert client.post("/api/campaigns/merge", json={"campaign_ids": ["camp-a", "camp-a"]}).status_code == 422
    assert client.post("/api/campaigns/split", json={
        "campaign_id": "camp-a", "incident_ids": ["inc-a", "inc-b"]
    }).status_code == 422
    assert client.post("/api/campaigns/split", json={
        "campaign_id": "camp-a", "incident_ids": ["inc-missing"]
    }).status_code == 404
