"""Unit tests for shared pipeline dataclasses."""

from __future__ import annotations

from backend.pipeline.models import (
    Artifact,
    ArtifactKind,
    Coverage,
    Evidence,
    EvidenceFamily,
    EvidenceTier,
    Incident,
    IncidentBundle,
    MediaRef,
    ParseStatus,
    funnel_step_from_name,
)


def test_evidence_includes_ignore_reason() -> None:
    ev = Evidence(
        type="cdn_ip",
        tier=EvidenceTier.B,
        family=EvidenceFamily.HOSTING,
        value_hash="abc",
        display="masked",
        ignored=True,
        ignore_reason="cdn_ip",
        artifact_id="art_1",
        funnel_step=2,
    )
    assert ev.ignored is True
    assert ev.ignore_reason == "cdn_ip"
    assert ev.funnel_step == 2


def test_incident_bundle_shape() -> None:
    incident = Incident(id="inc_1", folder="/tmp/x", title="x")
    bundle = IncidentBundle(
        incident=incident,
        artifacts=[
            Artifact(
                id="art_1",
                incident_id="inc_1",
                kind=ArtifactKind.TEXT,
                path="/tmp/x/note.txt",
                parse_status=ParseStatus.OK,
            )
        ],
        evidence=[],
        coverage=Coverage(kinds_present=["text"]),
        media=[
            MediaRef(
                id="m1",
                artifact_id="art_1",
                kind="frame",
                sha256="deadbeef",
                path="media/deadbeef.jpg",
            )
        ],
    )
    assert bundle.incident.id == "inc_1"
    assert bundle.media[0].path == "media/deadbeef.jpg"
    assert bundle.coverage.kinds_present == ["text"]


def test_funnel_step_from_name() -> None:
    assert funnel_step_from_name("strona_1") == 1
    assert funnel_step_from_name("STRONA_12") == 12
    assert funnel_step_from_name("strona_") is None
    assert funnel_step_from_name("other") is None
    assert funnel_step_from_name("strona_0") is None
