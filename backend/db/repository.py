"""Parameterized persistence boundary used by the ingestion pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import json
from pathlib import Path
import sqlite3
from typing import Any, Callable, Iterable
import uuid

from backend.pipeline.models import Artifact, Evidence, Incident, IncidentBundle, MediaRef

from .database import connect, init_db


def _scalar(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    return value


# Membership rows that belong to campaign-level groups (networks are kept on replay).
_CAMPAIGN_MEMBERSHIP = "campaign_id IN (SELECT id FROM campaigns WHERE level='campaign')"


class Repository:
    """Small repository with one transaction per public save operation."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        init_db(self.path)

    def _connection(self) -> sqlite3.Connection:
        return connect(self.path)

    def health_check(self) -> None:
        """Confirm the initialized SQLite database is readable and consistent."""
        with self._connection() as db:
            result = db.execute("PRAGMA quick_check").fetchone()
        if result is None or result[0] != "ok":
            raise sqlite3.DatabaseError("SQLite integrity check failed")

    def save_incident(self, incident: Incident) -> None:
        ingested_at = datetime.now(timezone.utc).isoformat()
        values = (
            incident.id, incident.folder, incident.title, _scalar(incident.first_seen),
            _scalar(incident.last_seen), json.dumps(incident.coverage.to_dict()), incident.status,
            ingested_at,
        )
        with self._connection() as db:
            db.execute("""INSERT INTO incidents
                (id,folder,title,first_seen,last_seen,coverage_json,status,ingested_at)
                VALUES (?,?,?,?,?,?,?,?)
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

    def save_artifact_details(self, requests: Iterable[dict[str, Any]],
                              redirects: Iterable[dict[str, Any]],
                              pages: Iterable[dict[str, Any]]) -> None:
        """Replace stored request, redirect and page rows for the given artifacts."""
        with self._connection() as db:
            self._replace_artifact_details(db, requests, redirects, pages)

    @staticmethod
    def _replace_artifact_details(db: sqlite3.Connection, requests: Iterable[dict[str, Any]],
                                  redirects: Iterable[dict[str, Any]],
                                  pages: Iterable[dict[str, Any]]) -> None:
        requests, redirects, pages = list(requests), list(redirects), list(pages)
        artifact_ids = sorted({row["artifact_id"] for row in (*requests, *redirects, *pages)})
        for table in ("requests", "redirect_hops", "pages"):
            db.executemany(f"DELETE FROM {table} WHERE artifact_id=?", [(i,) for i in artifact_ids])
        db.executemany("""INSERT INTO requests
            (artifact_id,seq,method,host,path_pattern,status,server_ip,mime) VALUES (?,?,?,?,?,?,?,?)""",
            [(r["artifact_id"], r["seq"], r["method"], r["host"], r["path_pattern"], r["status"],
              r["server_ip"], r["mime"]) for r in requests])
        db.executemany("""INSERT INTO redirect_hops (artifact_id,seq,url_display,status,kind)
            VALUES (?,?,?,?,?)""", [(r["artifact_id"], r["seq"], r["url_display"], r["status"], r["kind"])
                                    for r in redirects])
        db.executemany("""INSERT INTO pages (artifact_id,url_redacted,final_url,domain,title,role)
            VALUES (?,?,?,?,?,?)""", [(r["artifact_id"], r["url_redacted"], r["final_url"], r["domain"],
                                       r["title"], r["role"]) for r in pages])

    def artifact_details(self, artifact_ids: Iterable[str]) -> dict[str, dict[str, Any]]:
        """Pages, redirect hops, request count and hosts per artifact."""
        identifiers = sorted(set(artifact_ids))
        details: dict[str, dict[str, Any]] = {
            i: {"pages": [], "redirects": [], "request_count": 0, "hosts": []} for i in identifiers}
        if not identifiers:
            return details
        placeholders = ",".join("?" for _ in identifiers)
        with self._connection() as db:
            for row in db.execute(f"SELECT * FROM pages WHERE artifact_id IN ({placeholders}) ORDER BY id",
                                  identifiers):
                details[row["artifact_id"]]["pages"].append(dict(row))
            for row in db.execute(f"SELECT * FROM redirect_hops WHERE artifact_id IN ({placeholders}) "
                                  "ORDER BY artifact_id, seq", identifiers):
                details[row["artifact_id"]]["redirects"].append(dict(row))
            for row in db.execute(f"SELECT artifact_id, COUNT(*) AS n FROM requests WHERE artifact_id "
                                  f"IN ({placeholders}) GROUP BY artifact_id", identifiers):
                details[row["artifact_id"]]["request_count"] = row["n"]
            for row in db.execute(f"SELECT artifact_id, host, COUNT(*) AS n FROM requests WHERE artifact_id "
                                  f"IN ({placeholders}) AND host != '' GROUP BY artifact_id, host "
                                  "ORDER BY artifact_id, n DESC, host", identifiers):
                details[row["artifact_id"]]["hosts"].append(row["host"])
        return details

    def get_artifacts(self, incident_id: str) -> list[dict[str, Any]]:
        with self._connection() as db:
            rows = db.execute("SELECT * FROM artifacts WHERE incident_id=? ORDER BY id", (incident_id,))
            return [dict(row) for row in rows]

    def duplicate_artifact_map(self, artifacts: Iterable[dict[str, Any]]) -> dict[str, str]:
        """Map exact duplicate artifact IDs to the first recorded observation."""
        hashes = sorted({row["sha256"] for row in artifacts if row.get("sha256")})
        if not hashes:
            return {}
        placeholders = ",".join("?" for _ in hashes)
        with self._connection() as db:
            rows = db.execute(
                f"SELECT id,sha256 FROM artifacts WHERE sha256 IN ({placeholders}) ORDER BY rowid",
                hashes,
            ).fetchall()
        canonical: dict[str, str] = {}
        duplicates: dict[str, str] = {}
        for row in rows:
            digest, artifact_id = row["sha256"], row["id"]
            if digest in canonical:
                duplicates[artifact_id] = canonical[digest]
            else:
                canonical[digest] = artifact_id
        return duplicates

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

    def replace_incident_contents(self, incident_id: str, artifacts: Iterable[Artifact],
                                  evidence: Iterable[Evidence]) -> None:
        """Make stored artifacts and evidence match a fresh parse of the incident.

        A re-import recomputes everything, so evidence from an older run (or an
        older extractor) and artifacts no longer on disk must not linger.
        """
        keep = [item.id for item in artifacts]
        with self._connection() as db:
            placeholders = ",".join("?" for _ in keep) or "''"
            db.execute(f"DELETE FROM artifacts WHERE incident_id=? AND id NOT IN ({placeholders})",
                       (incident_id, *keep))
            db.execute("DELETE FROM evidence WHERE incident_id=?", (incident_id,))
        self.save_evidence(incident_id, evidence)

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

    def media_path_in_use(self, path: str) -> bool:
        with self._connection() as db:
            return db.execute("SELECT 1 FROM media WHERE path=? LIMIT 1", (path,)).fetchone() is not None

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
            rows = db.execute("""SELECT e.*,
                a.action AS override_action, a.created_at AS override_recorded_at,
                a.detail_json AS override_detail_json
                FROM edges e LEFT JOIN audit_log a ON a.id=(
                    SELECT MAX(history.id) FROM audit_log history
                    WHERE history.subject_id=e.id AND history.action IN ('edge.confirm','edge.reject')
                ) ORDER BY e.id""").fetchall()
        result = []
        for row in rows:
            edge = dict(row)
            action = edge.pop("override_action")
            recorded_at = edge.pop("override_recorded_at")
            detail_json = edge.pop("override_detail_json")
            edge["analyst_override"] = ({
                "decision": action.removeprefix("edge."),
                "recorded_at": recorded_at,
                "note": json.loads(detail_json or "{}").get("note"),
            } if action else None)
            result.append(edge)
        return result

    def list_campaigns(self) -> list[dict[str, Any]]:
        with self._connection() as db:
            return [dict(row) for row in db.execute("SELECT * FROM campaigns ORDER BY id")]

    def list_membership(self) -> list[dict[str, Any]]:
        with self._connection() as db:
            return [dict(row) for row in db.execute("SELECT * FROM membership ORDER BY campaign_id,incident_id")]

    def manual_campaign_ids(self) -> set[str]:
        """Return extant campaign IDs touched by analyst Merge/Split operations."""
        with self._connection() as db:
            campaigns = {row[0] for row in db.execute("SELECT id FROM campaigns WHERE level='campaign'")}
            rows = db.execute("""SELECT action,subject_id,detail_json FROM audit_log
                WHERE action IN ('campaign.merge','campaign.split') ORDER BY id""").fetchall()
        manual: set[str] = set()
        for row in rows:
            detail = json.loads(row["detail_json"] or "{}")
            if row["action"] == "campaign.merge":
                candidates = [row["subject_id"], *detail.get("campaign_ids", [])]
            else:
                candidates = [row["subject_id"], detail.get("new_campaign_id")]
            manual.update(identifier for identifier in candidates if identifier in campaigns)
        return manual

    def save_uploaded_bundle(self, bundle: IncidentBundle,
                             analysis: Callable[[], tuple[Iterable[Any], Iterable[Any], Iterable[dict[str, Any]]]]) -> None:
        """Serialize analysis and atomically add an upload with its derived state."""
        incident = bundle.incident
        now = datetime.now(timezone.utc).isoformat()
        incident_values = (
            incident.id, incident.folder, incident.title, _scalar(incident.first_seen),
            _scalar(incident.last_seen), json.dumps(incident.coverage.to_dict()), incident.status,
            now,
        )
        artifact_rows = [(
            item.id, item.incident_id, _scalar(item.kind), item.path, item.funnel_step,
            item.role, item.sha256, _scalar(item.captured_at), item.parser,
            _scalar(item.parse_status), item.error,
        ) for item in bundle.artifacts]
        evidence_rows = [(
            incident.id, item.artifact_id, item.type, _scalar(item.family), _scalar(item.tier),
            item.value_hash, item.display, item.weight, item.funnel_step, item.ignored,
            item.ignore_reason,
        ) for item in bundle.evidence]
        media_rows = [(item.id, item.artifact_id, item.kind, item.sha256, item.path,
                       item.phash, item.frame_ts, item.ocr_text) for item in bundle.media]
        detail = json.dumps({
            "artifact_count": len(artifact_rows),
            "evidence_count": len(evidence_rows),
            "media_count": len(media_rows),
        })
        with self._connection() as db:
            # Acquire the writer lock before reading existing memory so concurrent
            # uploads cannot replace derived state computed from the same snapshot.
            db.execute("PRAGMA busy_timeout = 30000")
            db.execute("BEGIN IMMEDIATE")
            edges, campaigns, decisions = analysis()
            db.execute("""INSERT INTO incidents
                (id,folder,title,first_seen,last_seen,coverage_json,status,ingested_at)
                VALUES (?,?,?,?,?,?,?,?)""", incident_values)
            db.executemany("""INSERT INTO artifacts
                (id,incident_id,kind,path,funnel_step,role,sha256,captured_at,parser,parse_status,error)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""", artifact_rows)
            db.executemany("""INSERT INTO evidence
                (incident_id,artifact_id,type,family,tier,value_hash,display_value,weight,
                 funnel_step,ignored,ignore_reason) VALUES (?,?,?,?,?,?,?,?,?,?,?)""", evidence_rows)
            db.executemany("INSERT INTO media VALUES (?,?,?,?,?,?,?,?)", media_rows)
            self._replace_artifact_details(db, bundle.requests, bundle.redirects, bundle.pages)
            self._replace_analysis(db, edges, campaigns, decisions)
            db.execute("INSERT INTO audit_log (created_at,action,subject_id,detail_json) VALUES (?,?,?,?)",
                (now, "incident.upload", incident.id, detail))

    def record_edge_decision(self, edge_id: str, decision: str, note: str | None = None) -> str | None:
        """Persist an analyst's decision for a stored edge and return its timestamp."""
        recorded_at = datetime.now(timezone.utc).isoformat()
        edge_status = "confirmed" if decision == "confirm" else "rejected"
        detail = {"decision": decision}
        if note:
            detail["note"] = note
        with self._connection() as db:
            if db.execute("SELECT 1 FROM edges WHERE id=?", (edge_id,)).fetchone() is None:
                return None
            db.execute("UPDATE edges SET status=? WHERE id=?", (edge_status, edge_id))
            db.execute("INSERT INTO audit_log (created_at,action,subject_id,detail_json) VALUES (?,?,?,?)",
                (recorded_at, f"edge.{decision}", edge_id, json.dumps(detail)))
        return recorded_at

    def merge_campaigns(self, campaign_ids: list[str], note: str | None = None) -> str:
        """Merge campaign memberships into the first selected campaign atomically."""
        identifiers = list(campaign_ids)
        if len(identifiers) < 2 or len(set(identifiers)) != len(identifiers):
            raise ValueError("Select at least two distinct campaigns")
        placeholders = ",".join("?" for _ in identifiers)
        with self._connection() as db:
            rows = db.execute(
                f"SELECT id,level FROM campaigns WHERE id IN ({placeholders})", identifiers
            ).fetchall()
            if len(rows) != len(identifiers):
                raise KeyError("Campaign not found")
            if any(row["level"] != "campaign" for row in rows):
                raise ValueError("Only campaign-level groups can be merged")

            target = identifiers[0]
            members = sorted({row["incident_id"] for row in db.execute(
                f"SELECT incident_id FROM membership WHERE campaign_id IN ({placeholders})", identifiers
            )})
            sources = identifiers[1:]
            if not members:
                raise ValueError("Selected campaigns have no members")

            db.execute(f"DELETE FROM membership WHERE campaign_id IN ({placeholders})", identifiers)
            db.executemany("INSERT INTO membership (campaign_id,incident_id,reason_json) VALUES (?,?,?)",
                [(target, incident_id, "{}") for incident_id in members])
            source_placeholders = ",".join("?" for _ in sources)
            db.execute(f"UPDATE decisions SET campaign_id=? WHERE campaign_id IN ({source_placeholders})",
                (target, *sources))
            db.execute(f"DELETE FROM campaigns WHERE id IN ({source_placeholders})", sources)

            detail = {"campaign_ids": identifiers, "incident_ids": members}
            if note:
                detail["note"] = note
            db.execute("INSERT INTO audit_log (created_at,action,subject_id,detail_json) VALUES (?,?,?,?)",
                (datetime.now(timezone.utc).isoformat(), "campaign.merge", target, json.dumps(detail)))
        return target

    def split_campaign(self, campaign_id: str, incident_ids: list[str], note: str | None = None) -> tuple[str, str]:
        """Move a proper subset of a campaign's members into a new campaign atomically."""
        selected = list(incident_ids)
        if not selected or len(set(selected)) != len(selected):
            raise ValueError("Select one or more distinct incidents")
        new_campaign_id = f"campaign-override-{uuid.uuid4().hex[:12]}"
        with self._connection() as db:
            row = db.execute("SELECT * FROM campaigns WHERE id=?", (campaign_id,)).fetchone()
            if row is None:
                raise KeyError("Campaign not found")
            if row["level"] != "campaign":
                raise ValueError("Only campaign-level groups can be split")
            members = {item["incident_id"] for item in db.execute(
                "SELECT incident_id FROM membership WHERE campaign_id=?", (campaign_id,)
            )}
            selected_set = set(selected)
            if not selected_set <= members:
                raise KeyError("Incident not found in this campaign")
            if len(selected_set) >= len(members):
                raise ValueError("Leave at least one incident in the original campaign")

            db.execute("INSERT INTO campaigns (id,level,label,profile_json,first_seen,last_seen) VALUES (?,?,?,?,?,?)",
                (new_campaign_id, "campaign", new_campaign_id, row["profile_json"], None, None))
            placeholders = ",".join("?" for _ in selected)
            db.execute(f"UPDATE membership SET campaign_id=? WHERE campaign_id=? AND incident_id IN ({placeholders})",
                (new_campaign_id, campaign_id, *selected))
            db.execute(f"UPDATE decisions SET campaign_id=? WHERE campaign_id=? AND incident_id IN ({placeholders})",
                (new_campaign_id, campaign_id, *selected))

            detail = {
                "new_campaign_id": new_campaign_id,
                "incident_ids": selected,
                "remaining_incident_ids": sorted(members - selected_set),
            }
            if note:
                detail["note"] = note
            db.execute("INSERT INTO audit_log (created_at,action,subject_id,detail_json) VALUES (?,?,?,?)",
                (datetime.now(timezone.utc).isoformat(), "campaign.split", campaign_id, json.dumps(detail)))
            self._assign_group_labels(db)
        return campaign_id, new_campaign_id

    def save_analysis(self, edges: Iterable[Any], campaigns: Iterable[Any],
                      decisions: Iterable[dict[str, Any]] = ()) -> None:
        """Replace derived engine state in one transaction."""
        with self._connection() as db:
            self._replace_analysis(db, edges, campaigns, decisions)

    @staticmethod
    def _replace_analysis(db: sqlite3.Connection, edges: Iterable[Any], campaigns: Iterable[Any],
                          decisions: Iterable[dict[str, Any]]) -> None:
        edge_rows = [(f"edge-{e.source}-{e.target}", e.source, e.target, e.level, e.score,
                      e.comparable, json.dumps([m.__dict__ for m in e.evidence]), "active") for e in edges]
        campaign_rows = [(c.id, c.level, c.id, json.dumps({"evidence_types": c.evidence_types,
            "families": c.families}), None, None) for c in campaigns]
        members = [(c.id, incident_id, "{}") for c in campaigns for incident_id in c.members]
        decision_rows = [(d["incident_id"], d["outcome"], d.get("campaign_id"),
                          json.dumps(d.get("reasons", [])), d["decided_at"]) for d in decisions]
        for table in ("decisions", "membership", "campaigns", "edges"):
            db.execute(f"DELETE FROM {table}")
        db.executemany("INSERT INTO edges VALUES (?,?,?,?,?,?,?,?)", edge_rows)
        db.executemany("INSERT INTO campaigns VALUES (?,?,?,?,?,?)", campaign_rows)
        db.executemany("INSERT INTO membership VALUES (?,?,?)", members)
        db.executemany("INSERT INTO decisions VALUES (?,?,?,?,?)", decision_rows)
        Repository._restore_manual_overrides(db)
        Repository._drop_empty_groups(db)
        Repository._assign_group_labels(db)

    @staticmethod
    def _drop_empty_groups(db: sqlite3.Connection) -> None:
        """Remove groups left without enough members after overrides were replayed."""
        db.execute("UPDATE decisions SET campaign_id=NULL WHERE campaign_id IN ("
                   "SELECT c.id FROM campaigns c WHERE NOT EXISTS ("
                   "SELECT 1 FROM membership m WHERE m.campaign_id=c.id))")
        db.execute("DELETE FROM campaigns WHERE NOT EXISTS ("
                   "SELECT 1 FROM membership m WHERE m.campaign_id=campaigns.id)")
        # A network groups several incidents; one left alone is no longer a network.
        db.execute("DELETE FROM campaigns WHERE level='network' AND ("
                   "SELECT COUNT(*) FROM membership m WHERE m.campaign_id=campaigns.id) < 2")

    @staticmethod
    def _assign_group_labels(db: sqlite3.Connection) -> None:
        """Give every group a number once and keep it, so labels do not shift."""
        known = {row["group_id"] for row in db.execute("SELECT group_id FROM group_labels")}
        for level in ("campaign", "network"):
            current = db.execute("SELECT COALESCE(MAX(number), 0) FROM group_labels WHERE level=?",
                                 (level,)).fetchone()[0]
            for row in db.execute("SELECT id FROM campaigns WHERE level=? ORDER BY first_seen, id",
                                  (level,)).fetchall():
                if row["id"] in known:
                    continue
                current += 1
                db.execute("INSERT INTO group_labels (group_id, level, number) VALUES (?,?,?)",
                           (row["id"], level, current))

    def group_labels(self) -> dict[str, tuple[str, int]]:
        with self._connection() as db:
            return {row["group_id"]: (row["level"], row["number"])
                    for row in db.execute("SELECT * FROM group_labels")}

    @staticmethod
    def _restore_manual_overrides(db: sqlite3.Connection) -> None:
        """Replay analyst decisions after rebuilding derived analysis state."""
        edge_overrides = db.execute(
            "SELECT subject_id,action FROM audit_log "
            "WHERE action IN ('edge.confirm','edge.reject') ORDER BY id"
        ).fetchall()
        for row in edge_overrides:
            db.execute("UPDATE edges SET status=? WHERE id=?",
                ("confirmed" if row["action"] == "edge.confirm" else "rejected", row["subject_id"]))

        actions = db.execute(
            "SELECT action,subject_id,detail_json FROM audit_log "
            "WHERE action IN ('campaign.merge','campaign.split') ORDER BY id"
        ).fetchall()
        for row in actions:
            detail = json.loads(row["detail_json"])
            if row["action"] == "campaign.merge":
                target = row["subject_id"]
                incident_ids = list(dict.fromkeys(detail.get("incident_ids", [])))
                if not target or not incident_ids:
                    continue
                campaign_ids = list(dict.fromkeys(detail.get("campaign_ids", [])))
                if target not in campaign_ids:
                    campaign_ids.insert(0, target)
                campaign_placeholders = ",".join("?" for _ in campaign_ids)
                current_members = [item["incident_id"] for item in db.execute(
                    f"SELECT incident_id FROM membership WHERE campaign_id IN ({campaign_placeholders})",
                    campaign_ids,
                )]
                incident_ids = list(dict.fromkeys([*incident_ids, *current_members]))
                placeholders = ",".join("?" for _ in incident_ids)
                profile = db.execute("SELECT profile_json FROM campaigns WHERE id=?", (target,)).fetchone()
                if profile is None:
                    profile = db.execute(
                        f"SELECT c.profile_json FROM campaigns c JOIN membership m ON m.campaign_id=c.id "
                        f"WHERE m.incident_id IN ({placeholders}) LIMIT 1", incident_ids
                    ).fetchone()
                profile_json = profile["profile_json"] if profile else "{}"
                db.execute("INSERT OR IGNORE INTO campaigns (id,level,label,profile_json,first_seen,last_seen) "
                    "VALUES (?, 'campaign', ?, ?, NULL, NULL)", (target, target, profile_json))
                db.execute(f"DELETE FROM membership WHERE incident_id IN ({placeholders}) "
                    f"AND {_CAMPAIGN_MEMBERSHIP}", incident_ids)
                db.executemany("INSERT OR IGNORE INTO membership (campaign_id,incident_id,reason_json) "
                    "VALUES (?,?,'{}')", [(target, identifier) for identifier in incident_ids
                                            if db.execute("SELECT 1 FROM incidents WHERE id=?", (identifier,)).fetchone()])
                db.execute(f"UPDATE decisions SET campaign_id=? WHERE incident_id IN ({placeholders}) "
                    "AND campaign_id IS NOT NULL", (target, *incident_ids))
                source_ids = [identifier for identifier in campaign_ids if identifier != target]
                if source_ids:
                    source_placeholders = ",".join("?" for _ in source_ids)
                    db.execute(f"DELETE FROM campaigns WHERE id IN ({source_placeholders})", source_ids)
            else:
                target = row["subject_id"]
                new_id = detail.get("new_campaign_id")
                incident_ids = list(dict.fromkeys(detail.get("incident_ids", [])))
                remaining_ids = list(dict.fromkeys(detail.get("remaining_incident_ids", [])))
                if not target or not new_id or not incident_ids:
                    continue
                target_row = db.execute("SELECT profile_json FROM campaigns WHERE id=?", (target,)).fetchone()
                profile_json = target_row["profile_json"] if target_row else "{}"
                db.execute("INSERT OR IGNORE INTO campaigns (id,level,label,profile_json,first_seen,last_seen) "
                    "VALUES (?, 'campaign', ?, ?, NULL, NULL)", (target, target, profile_json))
                db.execute("INSERT OR IGNORE INTO campaigns (id,level,label,profile_json,first_seen,last_seen) "
                    "VALUES (?, 'campaign', ?, ?, NULL, NULL)", (new_id, new_id, profile_json))
                all_ids = list(dict.fromkeys([*incident_ids, *remaining_ids]))
                placeholders = ",".join("?" for _ in all_ids)
                selected_placeholders = ",".join("?" for _ in incident_ids)
                db.execute(f"DELETE FROM membership WHERE incident_id IN ({placeholders}) "
                    f"AND {_CAMPAIGN_MEMBERSHIP}", all_ids)
                db.executemany("INSERT OR IGNORE INTO membership (campaign_id,incident_id,reason_json) "
                    "VALUES (?,?,'{}')", [(target, identifier) for identifier in remaining_ids
                                            if db.execute("SELECT 1 FROM incidents WHERE id=?", (identifier,)).fetchone()])
                db.executemany("INSERT OR IGNORE INTO membership (campaign_id,incident_id,reason_json) "
                    "VALUES (?,?,'{}')", [(new_id, identifier) for identifier in incident_ids
                                            if db.execute("SELECT 1 FROM incidents WHERE id=?", (identifier,)).fetchone()])
                if remaining_ids:
                    remaining_placeholders = ",".join("?" for _ in remaining_ids)
                    db.execute(f"UPDATE decisions SET campaign_id=? WHERE incident_id IN ({remaining_placeholders}) "
                        "AND campaign_id IS NOT NULL", (target, *remaining_ids))
                db.execute(f"UPDATE decisions SET campaign_id=? WHERE incident_id IN ({selected_placeholders}) "
                    "AND campaign_id IS NOT NULL", (new_id, *incident_ids))
