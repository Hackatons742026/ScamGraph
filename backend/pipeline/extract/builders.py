"""Shared Evidence builder with ignore annotation."""

from __future__ import annotations

from backend.pipeline.extract.ignore import ignore_reason_for
from backend.pipeline.models import Evidence, EvidenceFamily, EvidenceTier
from backend.pipeline.redact import hash_secret


def make_evidence(
    *,
    type: str,
    tier: EvidenceTier | str,
    family: EvidenceFamily | str | None,
    raw_value: str,
    display: str,
    artifact_id: str | None = None,
    funnel_step: int | None = None,
    host: str | None = None,
    ip: str | None = None,
    doc_bytes: int | None = None,
    salt: str | None = None,
    value_hash: str | None = None,
    weight: float = 0.0,
) -> Evidence:
    vh = value_hash or hash_secret(raw_value, salt=salt)
    reason = ignore_reason_for(
        evidence_type=type,
        display=display,
        value=raw_value,
        host=host,
        ip=ip,
        doc_bytes=doc_bytes,
    )
    return Evidence(
        type=type,
        tier=tier,
        family=family,
        value_hash=vh,
        display=display,
        weight=weight,
        artifact_id=artifact_id,
        funnel_step=funnel_step,
        ignored=reason is not None,
        ignore_reason=reason,
    )
