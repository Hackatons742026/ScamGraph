"""Deterministic, entirely synthetic contract fixtures."""

from .schemas import *  # noqa: F403

EVIDENCE = EvidenceItem(id="ev_demo", type="pixel_id", tier="A", family=None,
    display="pixel-****91", weight=1.2, artifact_id="art_demo", funnel_step=1,
    ignored=False, detail="exact salted-hash match")
COVERAGE = Coverage(artifact_kinds=["har"], has_har=True, has_page=False,
    has_image=False, has_video=False, has_adlib=False, has_text=True,
    level="ok", badges=[])
ARTIFACT = ArtifactSummary(id="art_demo", kind="har", name_display="capture.har",
    funnel_step=1, role="prelander", parse_status="ok", error=None,
    captured_at="2026-11-21T15:00:00Z", duplicate_of=None, observations=1)
INCIDENT = IncidentSummary(id="inc_demo", label="Synthetic incident",
    first_seen="2026-11-21T15:00:00Z", last_seen=None, artifact_count=1,
    coverage=COVERAGE, status="in_campaign", campaign_id="camp_demo",
    campaign_label="Synthetic campaign", network_id="net_demo",
    outcome="known_campaign", reason_summary="Synthetic tier-A match.")
EDGE = Edge(id="edge_demo", source="inc_demo", target="inc_peer", level="campaign",
    tier="A", families=[], score=1.2, comparable=2, low_confidence=False,
    evidence=[EVIDENCE])
INCIDENT_DETAIL = IncidentDetail(**INCIDENT.model_dump(), artifacts=[ARTIFACT], funnel=[],
    evidence=[EVIDENCE], decision=None, edges=[EDGE])
ARTIFACT_DETAIL = ArtifactDetail(**ARTIFACT.model_dump(), pages=[], redirect_chain=[],
    media=[], ocr_text=None, request_count=3, hosts_display=["example-****.test"])
CAMPAIGN = CampaignSummary(id="camp_demo", label="Synthetic campaign", level="campaign",
    size=1, incident_ids=["inc_demo"], first_seen="2026-11-21T15:00:00Z",
    last_seen=None, strongest_evidence=EVIDENCE, network_id="net_demo")
RUN = RunSummary(id="run_demo", status="done", started_at="2026-11-21T15:00:00Z",
    finished_at="2026-11-21T15:00:01Z", incidents=1, artifacts=1,
    artifacts_by_kind={"har": ArtifactKindStats(total=1, parsed=1, failed=0)},
    unique_artifacts=1, duplicates=0, campaigns=1, networks=1, unassigned=0,
    needs_review=0, new_candidates=0, secrets_redacted=2, error=None)
