import sqlite3

import pytest

from backend.db import Repository, init_db
from backend.pipeline.models import Artifact, Coverage, Evidence, Incident, MediaRef


def test_schema_is_repeatable_and_has_all_tables(tmp_path):
    path = tmp_path / "test.db"
    init_db(path)
    init_db(path)
    with sqlite3.connect(path) as db:
        names = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        media_columns = {row[1] for row in db.execute("PRAGMA table_info(media)")}
    assert {"runs", "incidents", "artifacts", "pages", "requests", "media", "evidence",
            "edges", "campaigns", "membership", "decisions", "audit_log"} <= names
    assert "path" in media_columns


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
