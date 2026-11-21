"""Public contract-v1 Pydantic models."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Tier = Enum("Tier", {x: x for x in ("A", "B", "C")}, type=str)
Family = Enum("Family", {x: x for x in ("kit", "tds", "domain", "creative", "hosting")}, type=str)
Level = Enum("Level", {x: x for x in ("campaign", "network")}, type=str)
Outcome = Enum("Outcome", {x: x for x in ("known_campaign", "new_candidate", "needs_review")}, type=str)
IncidentStatus = Enum("IncidentStatus", {x: x for x in ("in_campaign", "unassigned", "needs_review", "new_candidate")}, type=str)
ArtifactKind = Enum("ArtifactKind", {x: x for x in ("har", "html", "mhtml", "bundle", "image", "video", "adlib_json", "text", "url", "unknown")}, type=str)
ParseStatus = Enum("ParseStatus", {x: x for x in ("ok", "partial", "failed", "skipped")}, type=str)
FunnelRole = Enum("FunnelRole", {x: x for x in ("ad", "prelander", "offer", "order", "unknown")}, type=str)
CoverageLevel = Enum("CoverageLevel", {x: x for x in ("ok", "low")}, type=str)
RunStatus = Enum("RunStatus", {x: x for x in ("pending", "running", "done", "failed")}, type=str)
ReasonKind = Enum("ReasonKind", {x: x for x in ("match", "coverage", "conflict", "weak")}, type=str)

class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

class EvidenceItem(ContractModel):
    id: str; type: str; tier: Tier; family: Family | None; display: str; weight: float
    artifact_id: str; funnel_step: int | None; ignored: bool
    ignore_reason: str | None = None; detail: str | None = None

class Coverage(ContractModel):
    artifact_kinds: list[str]; has_har: bool; has_page: bool; has_image: bool
    has_video: bool; has_adlib: bool; has_text: bool
    level: CoverageLevel; badges: list[str]

class Reason(ContractModel):
    kind: ReasonKind
    text: str; evidence: list[EvidenceItem]

class Decision(ContractModel):
    outcome: Outcome; campaign_id: str | None; campaign_label: str | None
    reasons: list[Reason]; decided_at: str

class Edge(ContractModel):
    id: str; source: str; target: str; level: Level
    tier: Tier; families: list[str]; score: float; comparable: int
    low_confidence: bool; evidence: list[EvidenceItem]

class ArtifactSummary(ContractModel):
    id: str; kind: ArtifactKind; name_display: str; funnel_step: int | None
    role: FunnelRole | None
    parse_status: ParseStatus
    error: str | None; captured_at: str | None
    duplicate_of: str | None; observations: int

class RedirectHop(ContractModel):
    seq: int; url_display: str; status: int | None; kind: Literal["3xx", "meta", "js"]

class FunnelStep(ContractModel):
    step: int; role: str; artifact_ids: list[str]; domain_display: str | None
    redirect_chain: list[RedirectHop]

class Media(ContractModel):
    id: str; kind: Literal["screenshot", "frame", "image"]
    frame_ts: float | None; ocr_text: str | None; width: int; height: int

class IncidentSummary(ContractModel):
    id: str; label: str; first_seen: str | None; last_seen: str | None
    artifact_count: int; coverage: Coverage; status: IncidentStatus
    campaign_id: str | None; campaign_label: str | None; network_id: str | None
    outcome: Outcome | None; reason_summary: str | None = None

class IncidentDetail(IncidentSummary):
    artifacts: list[ArtifactSummary]; funnel: list[FunnelStep]
    evidence: list[EvidenceItem]; decision: Decision | None; edges: list[Edge]

class PageSummary(ContractModel):
    url_display: str; domain_display: str; title: str | None; role: str | None

class ArtifactDetail(ArtifactSummary):
    pages: list[PageSummary]; redirect_chain: list[RedirectHop]; media: list[Media]
    ocr_text: str | None; request_count: int; hosts_display: list[str]

class CampaignSummary(ContractModel):
    id: str; label: str; level: Level; size: int
    incident_ids: list[str]; first_seen: str | None; last_seen: str | None
    strongest_evidence: EvidenceItem | None; network_id: str | None

class TimelineItem(ContractModel):
    date: str; incident_id: str; event: str

class CampaignDetail(CampaignSummary):
    members: list[IncidentSummary]; edges: list[Edge]; timeline: list[TimelineItem]

class CampaignLink(ContractModel):
    other_id: str; other_label: str; level: Level
    shared_evidence: list[EvidenceItem]

class GraphNode(ContractModel):
    id: str; kind: Literal["incident", "campaign", "network", "unassigned"]
    label: str; parent: str | None; outcome: Outcome | None
    coverage_level: CoverageLevel | None

class GraphResponse(ContractModel):
    nodes: list[GraphNode]; edges: list[Edge]

class ArtifactKindStats(ContractModel):
    total: int; parsed: int; failed: int

class RunSummary(ContractModel):
    id: str; status: RunStatus
    started_at: str; finished_at: str | None; incidents: int; artifacts: int
    artifacts_by_kind: dict[str, ArtifactKindStats]; unique_artifacts: int
    duplicates: int; campaigns: int; networks: int; unassigned: int
    needs_review: int; new_candidates: int; secrets_redacted: int; error: str | None

class ClassifyResult(ContractModel):
    outcome: Outcome; campaign_id: str | None; campaign_label: str | None
    reasons: list[Reason]; coverage: Coverage; evidence: list[EvidenceItem]
    candidate_edges: list[Edge]; elapsed_ms: int

class MetricSet(ContractModel):
    precision: float; recall: float; f1: float; tp: int; fp: int; fn: int

class Scenario(ContractModel):
    id: int = Field(ge=1, le=7); name: str; criterion: str; passed: bool; details: str

class PairReport(ContractModel):
    n_pairs: int; mentor_verified: int; agreement: float | None
    campaign: MetricSet; network: MetricSet

class LooRow(ContractModel):
    incident_id: str; expected: Outcome; predicted: Outcome; correct: bool

class Confusion(ContractModel):
    labels: list[Outcome]; matrix: list[list[int]]

class LooReport(ContractModel):
    accuracy: float; rows: list[LooRow]; confusion: Confusion

class Ablation(ContractModel):
    config: str; campaign_p: float; campaign_r: float
    false_merges: int; loo_routing: float

class EvalReport(ContractModel):
    generated_at: str | None; scenarios: list[Scenario]; pairs: PairReport
    false_merges: int; loo: LooReport; ablation: list[Ablation]

class ImportAccepted(ContractModel):
    run_id: str

class ImportRequest(ContractModel):
    path: str | None = None

class ErrorResponse(ContractModel):
    error: str; detail: str
