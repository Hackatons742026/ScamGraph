"""Parameterized persistence boundary used by the ingestion pipeline."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable

from backend.pipeline.models import Artifact, Evidence, Incident, MediaRef

from .database import connect, init_db


def _scalar(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    return value


class Repository:
    """Small repository with one transaction per public save operation."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        init_db(self.path)

    def _connection(self) -> sqlite3.Connection:
        return connect(self.path)

    def save_incident(self, incident: Incident) -> None:
        values = (
            incident.id, incident.folder, incident.title, _scalar(incident.first_seen),
            _scalar(incident.last_seen), json.dumps(incident.coverage.to_dict()), incident.status,
        )
        with self._connection() as db:
            db.execute("""INSERT INTO incidents VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET folder=excluded.folder,title=excluded.title,
                first_seen=excluded.first_seen,last_seen=excluded.last_seen,
                coverage_json=excluded.coverage_json,status=excluded.status""", values)

    def get_incident(self, incident_id: str) -> dict[str, Any] | None:
        with self._connection() as db:
            row = db.execute("SELECT * FROM incidents WHERE id=?", (incident_id,)).fetchone()
        return dict(row) if row else None

    def save_artifacts(self, artifacts: Iterable[Artifact]) -> None:
        rows = [(
            item.id, item.incident_id, _scalar(item.kind), item.path, item.funnel_step,
            item.role, item.sha256, _scalar(item.captured_at), item.parser,
            _scalar(item.parse_status), item.error,
        ) for item in artifacts]
        with self._connection() as db:
            db.executemany("""INSERT INTO artifacts
                (id,incident_id,kind,path,funnel_step,role,sha256,captured_at,parser,parse_status,error)
                VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                incident_id=excluded.incident_id,kind=excluded.kind,path=excluded.path,
                funnel_step=excluded.funnel_step,role=excluded.role,sha256=excluded.sha256,
                captured_at=excluded.captured_at,parser=excluded.parser,
                parse_status=excluded.parse_status,error=excluded.error""", rows)

    def get_artifacts(self, incident_id: str) -> list[dict[str, Any]]:
        with self._connection() as db:
            rows = db.execute("SELECT * FROM artifacts WHERE incident_id=? ORDER BY id", (incident_id,))
            return [dict(row) for row in rows]

    def get_artifact(self, artifact_id: str) -> dict[str, Any] | None:
        with self._connection() as db:
            row = db.execute("SELECT * FROM artifacts WHERE id=?", (artifact_id,)).fetchone()
        return dict(row) if row else None

    def save_evidence(self, incident_id: str, evidence: Iterable[Evidence]) -> None:
        rows = [(
            incident_id, item.artifact_id, item.type, _scalar(item.family), _scalar(item.tier),
            item.value_hash, item.display, item.weight, item.funnel_step, item.ignored,
            item.ignore_reason,
        ) for item in evidence]
        with self._connection() as db:
            db.executemany("""INSERT INTO evidence
                (incident_id,artifact_id,type,family,tier,value_hash,display_value,weight,
                 funnel_step,ignored,ignore_reason) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT DO UPDATE SET family=excluded.family,tier=excluded.tier,
                display_value=excluded.display_value,weight=excluded.weight,
                ignored=excluded.ignored,ignore_reason=excluded.ignore_reason""", rows)

    def get_evidence(self, incident_id: str) -> list[dict[str, Any]]:
        with self._connection() as db:
            rows = db.execute("SELECT * FROM evidence WHERE incident_id=? ORDER BY id", (incident_id,))
            return [dict(row) for row in rows]

    def save_media(self, media: Iterable[MediaRef]) -> None:
        rows = [(m.id, m.artifact_id, m.kind, m.sha256, m.path, m.phash, m.frame_ts, m.ocr_text)
                for m in media]
        with self._connection() as db:
            db.executemany("INSERT OR REPLACE INTO media VALUES (?,?,?,?,?,?,?,?)", rows)

    def get_media(self, media_id: str) -> dict[str, Any] | None:
        with self._connection() as db:
            row = db.execute("SELECT * FROM media WHERE id=?", (media_id,)).fetchone()
        return dict(row) if row else None

    def list_media(self, artifact_id: str) -> list[dict[str, Any]]:
        with self._connection() as db:
            return [dict(row) for row in db.execute("SELECT * FROM media WHERE artifact_id=? ORDER BY id", (artifact_id,))]

    def save_run(self, run_id: str, status: str, started_at: str, *,
                 finished_at: str | None = None, summary: dict[str, Any] | None = None,
                 error: str | None = None) -> None:
        with self._connection() as db:
            db.execute("INSERT OR REPLACE INTO runs VALUES (?,?,?,?,?,?)", (
                run_id, status, started_at, finished_at, json.dumps(summary or {}), error,
            ))

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._connection() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        return dict(row) if row else None

    def delete_run(self, run_id: str) -> None:
        with self._connection() as db: db.execute("DELETE FROM runs WHERE id=?", (run_id,))

    def list_decisions(self) -> list[dict[str, Any]]:
        with self._connection() as db: return [dict(row) for row in db.execute("SELECT * FROM decisions ORDER BY incident_id")]

    def latest_run(self) -> dict[str, Any] | None:
        with self._connection() as db:
            row = db.execute("SELECT * FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()
        return dict(row) if row else None

    def list_incidents(self) -> list[dict[str, Any]]:
        with self._connection() as db:
            return [dict(row) for row in db.execute("SELECT * FROM incidents ORDER BY id")]

    def list_evidence(self) -> list[dict[str, Any]]:
        with self._connection() as db:
            return [dict(row) for row in db.execute("SELECT * FROM evidence ORDER BY incident_id,id")]

    def list_edges(self) -> list[dict[str, Any]]:
        with self._connection() as db:
            return [dict(row) for row in db.execute("SELECT * FROM edges ORDER BY id")]

    def list_campaigns(self) -> list[dict[str, Any]]:
        with self._connection() as db:
            return [dict(row) for row in db.execute("SELECT * FROM campaigns ORDER BY id")]

    def list_membership(self) -> list[dict[str, Any]]:
        with self._connection() as db:
            return [dict(row) for row in db.execute("SELECT * FROM membership ORDER BY campaign_id,incident_id")]

    def save_analysis(self, edges: Iterable[Any], campaigns: Iterable[Any],
                      decisions: Iterable[dict[str, Any]] = ()) -> None:
        """Replace derived engine state in one transaction."""
        edge_rows = [(f"edge-{e.source}-{e.target}", e.source, e.target, e.level, e.score,
                      e.comparable, json.dumps([m.__dict__ for m in e.evidence]), "active") for e in edges]
        campaign_rows = [(c.id, c.level, c.id, json.dumps({"evidence_types": c.evidence_types,
            "families": c.families}), None, None) for c in campaigns]
        members = [(c.id, incident_id, "{}") for c in campaigns for incident_id in c.members]
        decision_rows = [(d["incident_id"], d["outcome"], d.get("campaign_id"),
                          json.dumps(d.get("reasons", [])), d["decided_at"]) for d in decisions]
        with self._connection() as db:
            for table in ("decisions", "membership", "campaigns", "edges"):
                db.execute(f"DELETE FROM {table}")
            db.executemany("INSERT INTO edges VALUES (?,?,?,?,?,?,?,?)", edge_rows)
            db.executemany("INSERT INTO campaigns VALUES (?,?,?,?,?,?)", campaign_rows)
            db.executemany("INSERT INTO membership VALUES (?,?,?)", members)
            db.executemany("INSERT INTO decisions VALUES (?,?,?,?,?)", decision_rows)
