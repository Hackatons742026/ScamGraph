import sqlite3

import pytest

from backend.db import Repository, init_db
from backend.engine.linking import LinkEdge
from backend.engine.memory import Campaign
from backend.pipeline.models import Artifact, Coverage, Evidence, Incident, MediaRef


def test_schema_is_repeatable_and_has_all_tables(tmp_path):
    path = tmp_path / "test.db"
    init_db(path)
    init_db(path)
    with sqlite3.connect(path) as db:
        names = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        media_columns = {row[1] for row in db.execute("PRAGMA table_info(media)")}
        incident_columns = {row[1] for row in db.execute("PRAGMA table_info(incidents)")}
    assert {"runs", "incidents", "artifacts", "pages", "requests", "media", "evidence",
            "edges", "campaigns", "membership", "decisions", "audit_log"} <= names
    assert "path" in media_columns
    assert "ingested_at" in incident_columns


def test_legacy_incident_ingestion_time_stays_unknown(tmp_path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as db:
        db.execute("""CREATE TABLE incidents (
            id TEXT PRIMARY KEY, folder TEXT NOT NULL, title TEXT, first_seen TEXT,
            last_seen TEXT, coverage_json TEXT NOT NULL DEFAULT '{}', status TEXT)""")
        db.execute("INSERT INTO incidents (id,folder,first_seen) VALUES (?,?,?)",
                   ("legacy", "synthetic", "2026-01-01T00:00:00Z"))
    init_db(path)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT first_seen,ingested_at FROM incidents WHERE id='legacy'").fetchone() == (
            "2026-01-01T00:00:00Z", None)


def test_repository_round_trip_pipeline_models(tmp_path):
    repo = Repository(tmp_path / "test.db")
    incident = Incident("inc-1", "synthetic", coverage=Coverage(notes=["synthetic"]))
    repo.save_incident(incident)
    artifact = Artifact("art-1", incident.id, "har", "safe/example.har")
    repo.save_artifacts([artifact])
    evidence = Evidence("pixel_id", "A", None, "hash-only", "pixel-****", artifact_id=artifact.id)
    repo.save_evidence(incident.id, [evidence])
    evidence.weight = 2.0
    repo.save_evidence(incident.id, [evidence])
    media = MediaRef("media-1", artifact.id, "frame", "sha", path="media/sha.jpg")
    repo.save_media([media])
    repo.save_run("run-1", "done", "2026-01-01T00:00:00Z", summary={"incidents": 1})
    artifact.role = "prelander"
    repo.save_artifacts([artifact])

    assert repo.get_incident(incident.id)["folder"] == "synthetic"
    first_ingested_at = repo.get_incident(incident.id)["ingested_at"]
    assert first_ingested_at and incident.first_seen is None
    repo.save_incident(Incident(incident.id, "synthetic-updated"))
    assert repo.get_incident(incident.id)["ingested_at"] == first_ingested_at
    assert repo.get_artifacts(incident.id)[0]["kind"] == "har"
    assert repo.get_artifacts(incident.id)[0]["role"] == "prelander"
    assert repo.get_evidence(incident.id)[0]["display_value"] == "pixel-****"
    assert len(repo.get_evidence(incident.id)) == 1
    assert repo.get_evidence(incident.id)[0]["weight"] == 2.0
    assert repo.get_media(media.id)["path"] == "media/sha.jpg"
    assert repo.get_run("run-1")["status"] == "done"
    assert repo.get_incident("' OR 1=1 --") is None


def test_repository_enforces_foreign_keys(tmp_path):
    repo = Repository(tmp_path / "test.db")
    missing_parent = Artifact("orphan", "missing", "har", "safe/orphan.har")
    with pytest.raises(sqlite3.IntegrityError):
        repo.save_artifacts([missing_parent])


def test_repository_analysis_round_trip(tmp_path):
    repo = Repository(tmp_path / "test.db")
    for identifier in ("inc-a", "inc-b"):
        repo.save_incident(Incident(identifier, "synthetic"))
    edge = LinkEdge("inc-a", "inc-b", "campaign", "A", (), 1.0, 2, False, ())
    campaign = Campaign("campaign-inc-a", "campaign", ("inc-a", "inc-b"), (), ())
    repo.save_analysis([edge], [campaign])
    assert repo.list_edges()[0]["a_incident"] == "inc-a" and len(repo.list_membership()) == 2
    assert repo.list_campaigns()[0]["id"] == campaign.id
