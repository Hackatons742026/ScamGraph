"""Build a masked export projection from private repository rows."""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone

from backend.db import Repository
from backend.pipeline.redact import require_salt


class ExportNotFound(LookupError):
    """The requested campaign does not exist or is not exportable."""


def _ref(kind: str, value: str, salt: str) -> str:
    digest = hmac.new(salt.encode(), f"{kind}:{value}".encode(), hashlib.sha256).hexdigest()[:16]
    return f"{kind}-{digest}"


def campaign_export_projection(repo: Repository, campaign_id: str) -> dict:
    """Return export data with pseudonymous IDs and no raw values or paths."""
    salt = require_salt()
    campaign = next((row for row in repo.list_campaigns()
                     if row["id"] == campaign_id and row["level"] == "campaign"), None)
    if campaign is None:
        raise ExportNotFound(campaign_id)

    member_ids = sorted({row["incident_id"] for row in repo.list_membership()
                         if row["campaign_id"] == campaign_id})
    incident_rows = {identifier: repo.get_incident(identifier) for identifier in member_ids}
    artifacts: list[dict] = []
    artifact_refs: dict[str, dict] = {}
    evidence: list[dict] = []
    incidents: list[dict] = []

    for identifier in member_ids:
        incident = incident_rows[identifier]
        if incident is None:
            continue
        incident_ref = _ref("incident", identifier, salt)
        incidents.append({
            "ref": incident_ref,
            "first_seen": incident["first_seen"],
            "last_seen": incident["last_seen"],
        })
        for artifact in repo.get_artifacts(identifier):
            artifact_projection = {
                "ref": _ref("artifact", artifact["id"], salt),
                "incident_ref": incident_ref,
                "kind": artifact["kind"],
                "role": artifact["role"] or "unknown",
                "parse_status": artifact["parse_status"] or "partial",
                "funnel_step": artifact["funnel_step"],
            }
            artifacts.append(artifact_projection)
            artifact_refs[artifact["id"]] = artifact_projection
        for row in repo.get_evidence(identifier):
            if row["ignored"]:
                continue
            source_artifact = artifact_refs.get(row["artifact_id"])
            evidence.append({
                "incident_ref": incident_ref,
                "artifact_ref": _ref("artifact", row["artifact_id"], salt) if row["artifact_id"] else None,
                "artifact_kind": source_artifact["kind"] if source_artifact else None,
                "type": row["type"],
                "tier": row["tier"],
                "family": row["family"],
                "masked_ref": _ref("value", row["value_hash"], salt),
                "funnel_step": row["funnel_step"],
            })

    member_set = set(member_ids)
    edges = []
    for row in repo.list_edges():
        if (row["level"] != "campaign" or row["a_incident"] not in member_set
                or row["b_incident"] not in member_set):
            continue
        edges.append({
            "ref": _ref("edge", row["id"], salt),
            "source_ref": _ref("incident", row["a_incident"], salt),
            "target_ref": _ref("incident", row["b_incident"], salt),
            "level": row["level"],
            "score": row["score"],
            "comparable": row["comparable"],
        })

    timestamps = []
    for item in incidents:
        for key in ("first_seen", "last_seen"):
            value = item[key]
            if not value:
                continue
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except (TypeError, ValueError):
                continue
            if parsed.tzinfo is not None:
                timestamps.append(parsed.astimezone(timezone.utc))
    export_date = min(timestamps).date().isoformat() if timestamps else None
    campaign_ref = _ref("campaign", campaign_id, salt)
    return {
        "campaign_ref": campaign_ref,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": export_date,
        "incidents": incidents,
        "artifacts": artifacts,
        "evidence": evidence,
        "edges": edges,
    }
