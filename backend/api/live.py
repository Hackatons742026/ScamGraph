"""Projection layer from private SQLite rows to the masked public contract."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from backend.db import Repository
from backend.pipeline.extract.ignore import is_third_party_host
from backend.pipeline.run import process_input, run_on_data_dir
from backend.pipeline.models import Evidence, IncidentBundle
from backend.engine.linking import link_incidents
from backend.engine.memory import classify, cluster_incidents
from .schemas import *  # noqa: F403


def _safe_incident_label(title: str | None, index: int, identifier: str | None = None) -> str:
    """Prefer discover folder title; fall back when empty or path-like."""
    text = (title or "").strip()
    if text.casefold() == "uploaded material" and identifier:
        return f"Upload {identifier[-6:]}"
    if not text or any(ch in text for ch in "/\\:"):
        return f"Incident {index}"
    return text


def stable_campaign(result: object, clusters: object, incident_id: str) -> str | None: return clusters.campaign_by_incident.get(incident_id) if result.outcome == "known_campaign" else None
def repository() -> Repository | None:
    return Repository(os.environ["SCAMGRAPH_DB"]) if os.environ.get("SCAMGRAPH_DB") else None

def analysis_snapshot(repo: Repository, extra: IncidentBundle | None = None) -> tuple[
    list[Any], list[Any], list[dict[str, Any]], Any
]:
    """Build a complete derived analysis snapshot, optionally including an upload."""
    grouped: dict[str, list[Evidence]] = {row["id"]: [] for row in repo.list_incidents()}
    for row in repo.list_evidence():
        grouped[row["incident_id"]].append(Evidence(row["type"], row["tier"], row["family"],
            row["value_hash"], row["display_value"], row["weight"], row["artifact_id"],
            row["funnel_step"], bool(row["ignored"]), row["ignore_reason"]))
    if extra is not None:
        grouped[extra.incident.id] = extra.evidence

    edges = link_incidents(grouped)
    rejected = {
        f"edge-{row['a_incident']}-{row['b_incident']}"
        for row in repo.list_edges() if row.get("status") == "rejected"
    }
    active_edges = [edge for edge in edges if f"edge-{edge.source}-{edge.target}" not in rejected]
    clusters = cluster_incidents(grouped, active_edges)
    decided_at = datetime.now(timezone.utc).isoformat()
    decisions = []
    for identifier in grouped:
        member_of = clusters.campaign_by_incident.get(identifier)
        if member_of:
            # The stored decision must agree with the incident's campaign membership.
            decisions.append({"incident_id": identifier, "outcome": "known_campaign",
                "campaign_id": member_of, "reasons": [membership_reason(identifier, member_of,
                    active_edges, clusters)], "decided_at": decided_at})
            continue
        memory = cluster_incidents(grouped, active_edges, exclude_incident=identifier)
        result = classify(identifier, [edge for edge in active_edges if identifier in {edge.source, edge.target}],
            memory, coverage_ok=bool(grouped[identifier]), exclude_incident=identifier)
        decisions.append({"incident_id": identifier, "outcome": result.outcome,
            "campaign_id": map_campaign(result.campaign_id, memory, clusters.campaign_by_incident)
                if result.outcome == "known_campaign" else None,
            "reasons": list(result.reasons), "decided_at": decided_at})
    return edges, [*clusters.networks, *clusters.campaigns], decisions, clusters


def membership_reason(identifier: str, campaign_id: str, edges: list[Any], clusters: Any) -> str:
    links = [edge for edge in edges if identifier in {edge.source, edge.target}
             and clusters.campaign_by_incident.get(edge.target if edge.source == identifier else edge.source)
             == campaign_id and edge.level == "campaign"]
    strongest = "tier A" if any(edge.tier == "A" for edge in links) else "multiple evidence families"
    count = len({edge.target if edge.source == identifier else edge.source for edge in links})
    noun = "incident" if count == 1 else "incidents"
    return f"Grouped with {count} other {noun} in this campaign via {strongest}."


def map_campaign(campaign_id: str | None, memory: Any, campaign_by_incident: dict[str, str]) -> str | None:
    """Translate a campaign id from a leave-one-out memory to the stored group id."""
    if not campaign_id:
        return None
    members = [incident for incident, group in memory.campaign_by_incident.items() if group == campaign_id]
    return next((campaign_by_incident[m] for m in sorted(members) if m in campaign_by_incident), None)

def persist_upload(repo: Repository, bundle: IncidentBundle) -> None:
    """Store an uploaded incident and its refreshed analysis in one transaction."""
    repo.save_uploaded_bundle(bundle, lambda: analysis_snapshot(repo, bundle)[:3])

def discard_failed_upload(repo: Repository, bundle: IncidentBundle) -> None:
    """Remove this request's unindexed cache files after a database failure."""
    cache_root = Path(os.environ.get("SCAMGRAPH_CACHE_DIR") or "data/cache").resolve()
    classify_root = (cache_root / "classify").resolve()
    folder = Path(bundle.incident.folder).resolve()
    if folder.is_relative_to(classify_root) and folder.is_dir():
        parent = folder.parent
        shutil.rmtree(folder, ignore_errors=True)
        if parent.is_relative_to(classify_root):
            try:
                parent.rmdir()
            except OSError:
                pass
    for media in bundle.media:
        if not media.path or repo.media_path_in_use(media.path):
            continue
        raw = Path(media.path)
        candidate = raw if raw.is_absolute() else cache_root / raw
        resolved = candidate.resolve()
        if resolved.is_relative_to(cache_root) and resolved.is_file():
            try:
                resolved.unlink()
            except OSError:
                pass

def execute_import(repo: Repository, run_id: str, data_dir: str) -> None:
    started = datetime.now(timezone.utc).isoformat()
    try:
        repo.save_run(run_id, "running", started)
        summary = run_on_data_dir(data_dir, db_path=repo.path)
        repo.delete_run(summary["run_id"])
        edges, campaigns, decisions, clusters = analysis_snapshot(repo)
        repo.save_analysis(edges, campaigns, decisions)
        stats: dict[str, dict[str, int]] = {}
        for row in repo.list_incidents():
            identifier = row["id"]
            for item in repo.get_artifacts(identifier):
                value = stats.setdefault(item["kind"], {"total": 0, "parsed": 0, "failed": 0, "partial": 0})
                value["total"] += 1; value["failed" if item["parse_status"] == "failed" else "parsed"] += 1
                value["partial"] += item["parse_status"] == "partial"
        summary.update(campaigns=len(clusters.campaigns), networks=len(clusters.networks), unassigned=len(clusters.unassigned),
            new_candidates=sum(d["outcome"] == "new_candidate" for d in decisions),
            needs_review=sum(d["outcome"] == "needs_review" for d in decisions),
            artifacts_by_kind=stats)
        repo.save_run(run_id, "done", started, finished_at=datetime.now(timezone.utc).isoformat(), summary=summary)
    except Exception as exc:  # background job boundary
        repo.save_run(run_id, "failed", started, finished_at=datetime.now(timezone.utc).isoformat(), error=str(exc)[:500])
def coverage(raw: str) -> Coverage:
    """Coverage badges are the gaps that weaken a decision (``no HAR``, ``video only``)."""
    value = json.loads(raw or "{}")
    kinds = value.get("kinds_present", [])
    badges = [note for note in value.get("notes", []) if note in {"no HAR", "video only", "media only"}]
    if not kinds:
        badges = ["no artifacts"]
    badges = list(dict.fromkeys(badges))
    return Coverage(artifact_kinds=kinds, has_har="har" in kinds or ("bundle" in kinds and "no HAR" not in badges),
        has_page=any(x in kinds for x in ("html", "mhtml", "bundle")),
        has_image="image" in kinds, has_video="video" in kinds,
        has_adlib="adlib_json" in kinds, has_text="text" in kinds,
        level="low" if badges else "ok", badges=badges)
def run(row: dict) -> RunSummary:
    summary = json.loads(row["summary_json"] or "{}")
    artifacts = sum(item.get("artifacts", 0) for item in summary.get("details", []))
    return RunSummary(id=row["id"], status=row["status"], started_at=row["started_at"],
        finished_at=row["finished_at"], incidents=summary.get("incidents", 0), artifacts=artifacts,
        artifacts_by_kind=summary.get("artifacts_by_kind", {}), unique_artifacts=artifacts,
        duplicates=summary.get("duplicates", 0),
        campaigns=summary.get("campaigns", 0), networks=summary.get("networks", 0),
        unassigned=summary.get("unassigned", 0), needs_review=summary.get("needs_review", 0),
        new_candidates=summary.get("new_candidates", 0),
        secrets_redacted=summary.get("secrets_redacted", 0), error="Import failed" if row["error"] else None)
def group_context(repo: Repository) -> dict:
    """Index campaign/network membership and create safe display labels."""
    campaigns = repo.list_campaigns()
    memberships = repo.list_membership()
    incidents = sorted(repo.list_incidents(), key=lambda item: (item["first_seen"] or "", item["id"]))
    incident_labels = {
        item["id"]: _safe_incident_label(item.get("title"), index, item["id"])
        for index, item in enumerate(incidents, 1)
    }
    rows_by_id = {item["id"]: item for item in campaigns}
    labels: dict[str, str] = {}
    stored_labels = repo.group_labels()
    for level, prefix in (("campaign", "Campaign"), ("network", "Network")):
        ordered = sorted((item for item in campaigns if item["level"] == level),
                         key=lambda item: (item["first_seen"] or "", item["id"]))
        used = {number for group, (lvl, number) in stored_labels.items() if lvl == level}
        fallback = (n for n in range(1, len(ordered) + len(used) + 2) if n not in used)
        for item in ordered:
            # Stored numbers never shift after merges or splits; groups created by
            # older databases without a stored number get the next free one.
            number = stored_labels[item["id"]][1] if item["id"] in stored_labels else next(fallback)
            labels[item["id"]] = f"{prefix} {number}"
    members_by_group: dict[str, list[str]] = {item["id"]: [] for item in campaigns}
    campaign_by_incident: dict[str, str] = {}
    network_by_incident: dict[str, str] = {}
    for membership in memberships:
        group_id = membership["campaign_id"]
        group = rows_by_id.get(group_id)
        if not group:
            continue
        incident_id = membership["incident_id"]
        members_by_group[group_id].append(incident_id)
        if group["level"] == "campaign":
            campaign_by_incident[incident_id] = group_id
        elif group["level"] == "network":
            network_by_incident[incident_id] = group_id
    network_by_campaign = {}
    for group_id, members in members_by_group.items():
        if rows_by_id[group_id]["level"] == "campaign":
            network_id = next((network_by_incident[member] for member in members
                               if member in network_by_incident), None)
            network_by_campaign[group_id] = network_id
    return {"rows_by_id": rows_by_id, "labels": labels,
        "incident_labels": incident_labels,
        "members_by_group": members_by_group,
        "campaign_by_incident": campaign_by_incident,
        "network_by_incident": network_by_incident,
        "network_by_campaign": network_by_campaign,
        "manual_campaign_ids": repo.manual_campaign_ids()}


def incident(repo: Repository, row: dict, groups: dict | None = None) -> IncidentSummary:
    groups = groups or group_context(repo)
    campaign_id = groups["campaign_by_incident"].get(row["id"])
    network_id = groups["network_by_incident"].get(row["id"])
    label = groups["incident_labels"].get(row["id"], "Incident")
    decision = next((item for item in repo.list_decisions() if item["incident_id"] == row["id"]), None)
    reasons = json.loads(decision["reasons_json"]) if decision else []
    artifacts = repo.get_artifacts(row["id"])
    outcome = decision["outcome"] if decision else None
    status = "in_campaign" if campaign_id else outcome or "unassigned"
    return IncidentSummary(id=row["id"], label=label,
        first_seen=row["first_seen"], last_seen=row["last_seen"], artifact_count=len(artifacts),
        coverage=coverage(row["coverage_json"]), status=status, campaign_id=campaign_id,
        campaign_label=groups["labels"].get(campaign_id) if campaign_id else None,
        network_id=network_id, outcome=outcome,
        reason_summary=reasons[0] if reasons else None,
        ingested_at=row.get("ingested_at"))
def evidence(row: dict) -> EvidenceItem:
    return EvidenceItem(id=f"evidence-{row['id']}", type=row["type"], tier=row["tier"],
        family=row["family"], display=row["display_value"], weight=row["weight"],
        artifact_id=row["artifact_id"] or "", funnel_step=row["funnel_step"],
        ignored=bool(row["ignored"]), ignore_reason=row["ignore_reason"])
def artifact(row: dict, *, duplicate_of: str | None = None) -> ArtifactSummary:
    observations = 1
    error = row.get("error") or ""
    match = re.search(r"(?:^|;\s*)observations=(\d+)(?:$|;)", error)
    if match:
        observations = int(match.group(1))
        error = re.sub(r"(?:^|;\s*)observations=\d+(?=$|;)", "", error).strip(" ;")
    return ArtifactSummary(id=row["id"], kind=row["kind"],
        name_display=artifact_name(row), funnel_step=row["funnel_step"],
        role=row["role"] or "unknown", parse_status=row["parse_status"] or "partial",
        error=safe_artifact_error(row["kind"], row["parse_status"], error),
        captured_at=row["captured_at"], duplicate_of=duplicate_of,
        observations=observations)

def safe_artifact_error(kind: str, status: str | None, error: str | None) -> str | None:
    """Return a useful parser hint without exposing paths or exception details."""
    if not error:
        return None
    message = error.casefold()
    if kind == "video":
        if "ffmpeg not available" in message:
            return "Video saved, but no frames were extracted: ffmpeg is not installed on the server."
        return "Video frames could not be extracted. Check that the file is a playable MP4, MOV or WEBM video."
    if kind in {"har", "bundle"}:
        if status == "partial":
            return "Capture was only partly readable; some requests were skipped."
        return "Capture could not be parsed. Export it again as a valid HAR (JSON) file."
    if kind in {"html", "mhtml"}:
        return "Saved page could not be parsed. Save it again as a complete web page."
    if kind == "adlib_json":
        if "no ad_id/page_id" in message:
            return "Ad Library JSON has no ad or advertiser page ID."
        return "Ad Library JSON could not be parsed."
    if kind != "image":
        return "Parse failed"

    message = error.casefold()
    if any(token in message for token in (
        "unidentifiedimage", "cannot identify image", "malformed", "corrupt image",
        "image could not be decoded",
    )):
        return "Image could not be decoded. Upload a valid PNG, JPEG, or WEBP image."
    if status == "failed":
        return "Image could not be processed. Verify that it is a valid PNG, JPEG, or WEBP image."
    if "no ocr engine" in message or "tesseract" in message or "pol failed" in message:
        return "Image saved, but Polish OCR is unavailable. Install Tesseract with Polish language data."
    if "preprocess unavailable" in message:
        return "Image could not be decoded or prepared. Check that it is a valid PNG, JPEG, or WEBP image."
    return "Image saved, but optional OCR processing was incomplete."

_KIND_NAMES = {"text": "Pasted text", "url": "Submitted URL", "bundle": "Capture bundle"}


def artifact_name(row: dict) -> str:
    """File name only (never the folder path) so analysts can tell artifacts apart."""
    kind = row["kind"]
    if kind in _KIND_NAMES:
        return _KIND_NAMES[kind]
    name = Path(str(row.get("path") or "")).name.strip()
    if not name or name.startswith("."):
        return f"{kind.upper() if kind == 'har' else kind.replace('_', ' ').capitalize()} file"
    return name if len(name) <= 80 else f"{name[:38]}…{name[-38:]}"


_ROLE_ORDER = {"ad": 1, "prelander": 2, "offer": 3, "order": 4}


def funnel(artifacts: list[ArtifactSummary], details: dict[str, dict]) -> list[FunnelStep]:
    """Funnel steps from ``strona_N`` folders, or from artifact roles when there are none."""
    stepped = [a for a in artifacts if a.funnel_step is not None]
    groups: dict[int, list[ArtifactSummary]] = {}
    if stepped:
        for item in stepped:
            groups.setdefault(item.funnel_step, []).append(item)
    else:
        roles = sorted({a.role.value if hasattr(a.role, "value") else a.role for a in artifacts} & set(_ROLE_ORDER),
                       key=_ROLE_ORDER.get)
        for index, role in enumerate(roles, 1):
            groups[index] = [a for a in artifacts if (a.role.value if hasattr(a.role, "value") else a.role) == role]
    steps = []
    for number in sorted(groups):
        items = groups[number]
        roles = [a.role.value if hasattr(a.role, "value") else a.role for a in items]
        known = [r for r in roles if r in _ROLE_ORDER]
        role = min(known, key=_ROLE_ORDER.get) if known else "unknown"
        # Ad-tech pixels redirect too; the funnel lists only the scam pages' own hops.
        hops = [hop for a in items for hop in details.get(a.id, {}).get("redirects", [])
                if not is_third_party_host(urlsplit(hop["url_display"]).hostname)]
        domain = next((p["domain"] for a in items for p in details.get(a.id, {}).get("pages", [])
                       if p.get("domain")), None)
        steps.append(FunnelStep(step=number, role=role, artifact_ids=[a.id for a in items],
            domain_display=domain, redirect_chain=[redirect_hop(hop) for hop in hops][:50]))
    return steps


def redirect_hop(row: dict) -> RedirectHop:
    kind = row.get("kind") if row.get("kind") in {"3xx", "meta", "js"} else "3xx"
    return RedirectHop(seq=row["seq"], url_display=row["url_display"], status=row.get("status"), kind=kind)


def page_summary(row: dict) -> PageSummary:
    return PageSummary(url_display=row.get("final_url") or row.get("url_redacted") or "",
        domain_display=row.get("domain") or "", title=row.get("title"), role=row.get("role"))


def media_size(row: dict) -> tuple[int, int]:
    """Pixel size of a cached media file; (0, 0) when it cannot be read."""
    try:
        from PIL import Image
        with Image.open(safe_media_path(row)) as opened:
            return opened.size
    except Exception:  # noqa: BLE001 — missing files or optional Pillow must not fail the API
        return 0, 0


def campaign_links(repo: Repository, campaign_id: str, groups: dict) -> list[CampaignLink]:
    """Other groups connected to this one by at least one non-rejected edge."""
    members = set(groups["members_by_group"].get(campaign_id, []))
    level = groups["rows_by_id"][campaign_id]["level"]
    shared: dict[str, list[EvidenceItem]] = {}
    for row in repo.list_edges():
        if row.get("status") == "rejected":
            continue
        ends = {row["a_incident"], row["b_incident"]}
        inside = ends & members
        if len(inside) != 1:
            continue
        other = next(iter(ends - members))
        if level == "campaign":
            other_group = groups["campaign_by_incident"].get(other) or groups["network_by_incident"].get(other)
        else:
            other_group = groups["network_by_incident"].get(other) or groups["campaign_by_incident"].get(other)
        if not other_group or other_group == campaign_id:
            continue
        items = shared.setdefault(other_group, [])
        seen = {(item.type, item.display) for item in items}
        for item in edge(row).evidence:
            if (item.type, item.display) not in seen:
                items.append(item)
                seen.add((item.type, item.display))
    tier_rank = {"A": 0, "B": 1, "C": 2}
    return [CampaignLink(other_id=group_id, other_label=groups["labels"].get(group_id, group_id),
                level=groups["rows_by_id"][group_id]["level"],
                shared_evidence=sorted(items, key=lambda i: tier_rank.get(getattr(i.tier, "value", i.tier), 3))[:20])
            for group_id, items in sorted(shared.items(), key=lambda pair: groups["labels"].get(pair[0], pair[0]))]


def edge(row: dict) -> Edge:
    raw = json.loads(row["evidence_json"] or "[]")
    tiers = [item.get("tier", "C") for item in raw]
    families = sorted({item["family"] for item in raw if item.get("family")})
    tier = "A" if "A" in tiers else "B" if "B" in tiers else "C"
    items = [EvidenceItem(id=f"{row['id']}-evidence-{index}", type=item["type"],
        tier=item.get("tier", "C"), family=item.get("family"), display=item.get("display", ""),
        weight=item.get("weight", 0.0), artifact_id=next(iter(item.get("artifact_ids", [])), ""),
        funnel_step=next(iter(item.get("funnel_steps", [])), None), ignored=False,
        ignore_reason=None, detail=item.get("detail")) for index, item in enumerate(raw)]
    return Edge(id=row["id"], source=row["a_incident"], target=row["b_incident"],
        level=row["level"], tier=tier, families=families, score=row["score"],
        comparable=row["comparable"], low_confidence=row["comparable"] < 2, evidence=items,
        analyst_override=row.get("analyst_override"))
def campaign(repo: Repository, row: dict, groups: dict | None = None) -> CampaignSummary:
    groups = groups or group_context(repo)
    members = sorted(groups["members_by_group"].get(row["id"], []))
    member_rows = [repo.get_incident(identifier) for identifier in members]
    seen = [item[key] for item in member_rows if item for key in ("first_seen", "last_seen") if item[key]]
    candidate_evidence = [item for identifier in members for item in repo.get_evidence(identifier)
                          if not item["ignored"]]
    strongest = max(candidate_evidence, key=lambda item: (
        {"A": 3, "B": 2, "C": 1}.get(item["tier"], 0), item["weight"], -item["id"])) if candidate_evidence else None
    return CampaignSummary(id=row["id"], label=groups["labels"].get(row["id"], row["label"]),
        level=row["level"], size=len(members), incident_ids=members,
        first_seen=min(seen) if seen else None, last_seen=max(seen) if seen else None,
        strongest_evidence=evidence(strongest) if strongest else None,
        network_id=groups["network_by_campaign"].get(row["id"]),
        membership_source="manual" if row["id"] in groups["manual_campaign_ids"] else "automatic")
def safe_media_path(row: dict) -> Path:
    roots = [Path(value).resolve() for key in ("SCAMGRAPH_DATA_DIR", "SCAMGRAPH_CACHE_DIR")
             if (value := os.environ.get(key))]
    raw_path = row.get("path")
    if not raw_path:
        raise FileNotFoundError
    path = Path(raw_path)
    candidates = [(root, path if path.is_absolute() else root / path) for root in roots]
    for root, candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file() and resolved.is_relative_to(root):
            return resolved
    raise FileNotFoundError
def _limit_mb(name: str, default: int) -> int:
    try:
        return max(1, int(os.environ.get(name, default)))
    except ValueError:
        return default


def upload_limits() -> tuple[int, int]:
    """(per-file, per-request) byte limits; real HAR captures and videos are often >5 MB."""
    per_file = _limit_mb("SCAMGRAPH_MAX_UPLOAD_FILE_MB", 50) * 1024 * 1024
    per_request = _limit_mb("SCAMGRAPH_MAX_UPLOAD_REQUEST_MB", 100) * 1024 * 1024
    return per_file, max(per_file, per_request)


def classify_multipart(repo: Repository, body: bytes, content_type: str,
                       exclude: str | None = None) -> tuple[object, object, list]:
    per_file, per_request = upload_limits()
    if len(body) > per_request: raise OverflowError
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
                if not safe or len(value) > per_file: raise OverflowError
                path = Path(directory) / safe; path.write_bytes(value); paths.append(path)
            elif name and name.group(1) in {b"text", b"url"} and value.strip():
                if name.group(1) == b"text": text = value.decode(errors="replace")
                else: url = value.decode(errors="replace")
        bundle = process_input(paths, text, url)
    # `process_input` intentionally gives its temporary folder a generic name;
    # assign every live upload a fresh resource id before storing it.
    bundle.incident.id = f"inc_{uuid.uuid4().hex[:12]}"
    bundle.incident.title = "Uploaded material"
    for item in bundle.artifacts:
        item.incident_id = bundle.incident.id
    for item in bundle.incident.artifacts:
        item.incident_id = bundle.incident.id
    grouped: dict[str, list[Evidence]] = {row["id"]: [] for row in repo.list_incidents()}
    for row in repo.list_evidence():
        grouped[row["incident_id"]].append(Evidence(row["type"], row["tier"], row["family"],
            row["value_hash"], row["display_value"], row["weight"], row["artifact_id"], row["funnel_step"]))
    edges = link_incidents({**grouped, bundle.incident.id: bundle.evidence})
    rejected = {
        f"edge-{row['a_incident']}-{row['b_incident']}"
        for row in repo.list_edges() if row.get("status") == "rejected"
    }
    active_edges = [edge for edge in edges if f"edge-{edge.source}-{edge.target}" not in rejected]
    memory = cluster_incidents(grouped, [e for e in active_edges if bundle.incident.id not in {e.source, e.target}],
                               exclude_incident=exclude)
    # Leave-one-out must not reveal links to the incident it hides.
    candidate = [e for e in active_edges if bundle.incident.id in {e.source, e.target}
                 and (not exclude or exclude not in {e.source, e.target})]
    result = classify(bundle.incident.id, candidate, memory,
        coverage_ok=bool(bundle.coverage.kinds_present), exclude_incident=exclude)
    if result.outcome == "known_campaign":
        # Memory clusters are rebuilt per request; report the stored group the analyst sees.
        stored = group_context(repo)["campaign_by_incident"]
        result = type(result)(result.outcome, map_campaign(result.campaign_id, memory, stored), result.reasons)
    return result, bundle, candidate


def unreadable_artifact_reasons(bundle: IncidentBundle) -> list[str]:
    """Safe, actionable notes for uploaded files that could not be fully parsed."""
    notes = []
    for item in bundle.artifacts:
        status = getattr(item.parse_status, "value", item.parse_status)
        if status not in {"failed", "partial"} or not item.error:
            continue
        kind = getattr(item.kind, "value", item.kind)
        message = safe_artifact_error(kind, status, item.error)
        if message:
            notes.append(f"{artifact_name({'kind': kind, 'path': item.path})}: {message}")
    return notes
