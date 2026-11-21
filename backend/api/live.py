"""Projection layer from private SQLite rows to the masked public contract."""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from backend.db import Repository
from backend.pipeline.run import run_on_data_dir
from backend.pipeline.run import process_input
from backend.pipeline.models import Evidence
from backend.engine.linking import link_incidents
from backend.engine.memory import classify, cluster_incidents

from .schemas import *  # noqa: F403


def repository() -> Repository | None:
    path = os.environ.get("SCAMGRAPH_DB")
    return Repository(path) if path else None


def execute_import(repo: Repository, run_id: str, data_dir: str) -> None:
    started = datetime.now(timezone.utc).isoformat()
    try:
        summary = run_on_data_dir(data_dir, db_path=repo.path)
        grouped: dict[str, list[Evidence]] = {row["id"]: [] for row in repo.list_incidents()}
        for row in repo.list_evidence():
            grouped[row["incident_id"]].append(Evidence(row["type"], row["tier"], row["family"],
                row["value_hash"], row["display_value"], row["weight"], row["artifact_id"],
                row["funnel_step"], bool(row["ignored"]), row["ignore_reason"]))
        edges = link_incidents(grouped)
        clusters = cluster_incidents(grouped, edges)
        repo.save_analysis(edges, [*clusters.networks, *clusters.campaigns])
        summary.update(campaigns=len(clusters.campaigns), networks=len(clusters.networks),
                       unassigned=len(clusters.unassigned))
        repo.save_run(run_id, "done", started, finished_at=datetime.now(timezone.utc).isoformat(), summary=summary)
    except Exception as exc:  # background job boundary
        repo.save_run(run_id, "failed", started, finished_at=datetime.now(timezone.utc).isoformat(), error=str(exc)[:500])


def coverage(raw: str) -> Coverage:
    value = json.loads(raw or "{}")
    kinds = value.get("kinds_present", [])
    badges = value.get("kinds_missing", []) + value.get("notes", [])
    return Coverage(artifact_kinds=kinds, has_har="har" in kinds,
        has_page=any(x in kinds for x in ("html", "mhtml", "bundle")),
        has_image="image" in kinds, has_video="video" in kinds,
        has_adlib="adlib_json" in kinds, has_text="text" in kinds,
        level="low" if badges else "ok", badges=badges)


def run(row: dict) -> RunSummary:
    summary = json.loads(row["summary_json"] or "{}")
    artifacts = sum(item.get("artifacts", 0) for item in summary.get("details", []))
    return RunSummary(id=row["id"], status=row["status"], started_at=row["started_at"],
        finished_at=row["finished_at"], incidents=summary.get("incidents", 0), artifacts=artifacts,
        artifacts_by_kind={}, unique_artifacts=artifacts, duplicates=0,
        campaigns=summary.get("campaigns", 0), networks=summary.get("networks", 0),
        unassigned=summary.get("unassigned", 0), needs_review=summary.get("needs_review", 0),
        new_candidates=summary.get("new_candidates", 0), secrets_redacted=0, error=row["error"])


def incident(repo: Repository, row: dict) -> IncidentSummary:
    memberships = {item["incident_id"]: item["campaign_id"] for item in repo.list_membership()}
    campaign_id = memberships.get(row["id"])
    artifacts = repo.get_artifacts(row["id"])
    status = "in_campaign" if campaign_id else "unassigned"
    return IncidentSummary(id=row["id"], label=row["title"] or "Incident",
        first_seen=row["first_seen"], last_seen=row["last_seen"], artifact_count=len(artifacts),
        coverage=coverage(row["coverage_json"]), status=status, campaign_id=campaign_id,
        campaign_label=campaign_id, network_id=None, outcome=None)


def evidence(row: dict) -> EvidenceItem:
    return EvidenceItem(id=f"evidence-{row['id']}", type=row["type"], tier=row["tier"],
        family=row["family"], display=row["display_value"], weight=row["weight"],
        artifact_id=row["artifact_id"] or "", funnel_step=row["funnel_step"],
        ignored=bool(row["ignored"]), ignore_reason=row["ignore_reason"])


def artifact(row: dict) -> ArtifactSummary:
    observations = 1
    if row["error"] and "observations=" in row["error"]:
        observations = int(row["error"].rsplit("observations=", 1)[1].split(";", 1)[0])
    return ArtifactSummary(id=row["id"], kind=row["kind"],
        name_display=Path(row["path"]).name, funnel_step=row["funnel_step"],
        role=row["role"] or "unknown", parse_status=row["parse_status"] or "partial",
        error=row["error"], captured_at=row["captured_at"], duplicate_of=None,
        observations=observations)


def edge(row: dict) -> Edge:
    raw = json.loads(row["evidence_json"] or "[]")
    tiers = [item.get("tier", "C") for item in raw]
    families = sorted({item["family"] for item in raw if item.get("family")})
    tier = "A" if "A" in tiers else "B" if "B" in tiers else "C"
    return Edge(id=row["id"], source=row["a_incident"], target=row["b_incident"],
        level=row["level"], tier=tier, families=families, score=row["score"],
        comparable=row["comparable"], low_confidence=row["comparable"] < 2, evidence=[])


def campaign(repo: Repository, row: dict) -> CampaignSummary:
    members = [m["incident_id"] for m in repo.list_membership() if m["campaign_id"] == row["id"]]
    return CampaignSummary(id=row["id"], label=row["label"], level=row["level"], size=len(members),
        incident_ids=members, first_seen=row["first_seen"], last_seen=row["last_seen"],
        strongest_evidence=None, network_id=None)


def safe_media_path(row: dict) -> Path:
    path = Path(row.get("path") or "").resolve()
    roots = [Path(value).resolve() for key in ("SCAMGRAPH_DATA_DIR", "SCAMGRAPH_CACHE_DIR")
             if (value := os.environ.get(key))]
    if not path.is_file() or not any(path.is_relative_to(root) for root in roots):
        raise FileNotFoundError
    return path


def classify_multipart(repo: Repository, body: bytes, content_type: str,
                       exclude: str | None = None) -> tuple[object, object, list]:
    if len(body) > 10_000_000: raise OverflowError
    boundary = re.search(r"boundary=([^;]+)", content_type)
    if not boundary: raise ValueError
    text = url = None
    with tempfile.TemporaryDirectory() as directory:
        paths = []
        for part in body.split(("--" + boundary.group(1).strip('"')).encode()):
            if b"\r\n\r\n" not in part: continue
            header, value = part.split(b"\r\n\r\n", 1); value = value.removesuffix(b"\r\n")
            name = re.search(rb'name="([^"]+)"', header)
            filename = re.search(rb'filename="([^"]*)"', header)
            if filename and value:
                safe = Path(filename.group(1).decode(errors="ignore")).name
                if not safe or len(value) > 5_000_000: raise OverflowError
                path = Path(directory) / safe; path.write_bytes(value); paths.append(path)
            elif name and name.group(1) in {b"text", b"url"} and value.strip():
                if name.group(1) == b"text": text = value.decode(errors="replace")
                else: url = value.decode(errors="replace")
        bundle = process_input(paths, text, url)
    grouped: dict[str, list[Evidence]] = {row["id"]: [] for row in repo.list_incidents()}
    for row in repo.list_evidence():
        grouped[row["incident_id"]].append(Evidence(row["type"], row["tier"], row["family"],
            row["value_hash"], row["display_value"], row["weight"], row["artifact_id"], row["funnel_step"]))
    edges = link_incidents({**grouped, bundle.incident.id: bundle.evidence})
    memory = cluster_incidents(grouped, [e for e in edges if bundle.incident.id not in {e.source, e.target}],
                               exclude_incident=exclude)
    candidate = [e for e in edges if bundle.incident.id in {e.source, e.target}]
    result = classify(bundle.incident.id, candidate, memory,
        coverage_ok=bool(bundle.coverage.kinds_present), exclude_incident=exclude)
    return result, bundle, candidate
