"""Contract-v1 endpoints backed by synthetic seed objects."""

import re
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response, status
from fastapi.responses import FileResponse

from . import seed
from . import live
from .schemas import *  # noqa: F403
from backend.eval import build_report

ERRORS = {code: {"model": ErrorResponse} for code in (404, 413, 422, 501)}
router = APIRouter(prefix="/api", responses=ERRORS)

@router.post("/import", response_model=ImportAccepted, status_code=202)
def start_import(background: BackgroundTasks, _request: ImportRequest | None = None) -> ImportAccepted:
    if repo := live.repository():
        data_dir = os.environ.get("SCAMGRAPH_DATA_DIR")
        if not data_dir: raise HTTPException(422, "SCAMGRAPH_DATA_DIR is not configured")
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        repo.save_run(run_id, "pending", datetime.now(timezone.utc).isoformat())
        background.add_task(live.execute_import, repo, run_id, data_dir)
        return ImportAccepted(run_id=run_id)
    return ImportAccepted(run_id=seed.RUN.id)

@router.get("/runs/latest", response_model=RunSummary)
def latest_run() -> RunSummary:
    if repo := live.repository():
        if row := repo.latest_run(): return live.run(row)
        raise HTTPException(404, "Run not found")
    return seed.RUN

@router.get("/runs/{run_id}", response_model=RunSummary)
def get_run(run_id: str) -> RunSummary:
    if repo := live.repository():
        if row := repo.get_run(run_id): return live.run(row)
        raise HTTPException(404, "Run not found")
    if run_id != seed.RUN.id: raise HTTPException(404, "Run not found")
    return seed.RUN

@router.get("/incidents", response_model=list[IncidentSummary])
def incidents(status: str | None = None, campaign: str | None = None) -> list[IncidentSummary]:
    if repo := live.repository():
        items = [live.incident(repo, row) for row in repo.list_incidents()]
        return [item for item in items if (not status or item.status.value in status.split(","))
                and (not campaign or item.campaign_id == campaign)]
    item = seed.INCIDENT
    return [item] if (not status or item.status in status.split(",")) and (not campaign or item.campaign_id == campaign) else []

@router.get("/incidents/{incident_id}", response_model=IncidentDetail)
def incident(incident_id: str) -> IncidentDetail:
    if repo := live.repository():
        row = repo.get_incident(incident_id)
        if not row: raise HTTPException(404, "Incident not found")
        item = live.incident(repo, row)
        artifacts = [live.artifact(a) for a in repo.get_artifacts(incident_id)]
        evidence = [live.evidence(e) for e in repo.get_evidence(incident_id)]
        edges = [live.edge(e) for e in repo.list_edges()
                 if incident_id in {e["a_incident"], e["b_incident"]}]
        decision_row = next((d for d in repo.list_decisions() if d["incident_id"] == incident_id), None)
        decision = Decision(outcome=decision_row["outcome"], campaign_id=decision_row["campaign_id"],
            campaign_label=decision_row["campaign_id"], reasons=[], decided_at=decision_row["decided_at"]) if decision_row else None
        return IncidentDetail(**item.model_dump(), artifacts=artifacts, funnel=[], evidence=evidence,
            decision=decision, edges=edges)
    if incident_id != seed.INCIDENT.id: raise HTTPException(404, "Incident not found")
    return seed.INCIDENT_DETAIL

@router.get("/artifacts/{artifact_id}", response_model=ArtifactDetail)
def artifact(artifact_id: str) -> ArtifactDetail:
    if repo := live.repository():
        row = repo.get_artifact(artifact_id)
        if not row: raise HTTPException(404, "Artifact not found")
        item = live.artifact(row)
        media = repo.list_media(artifact_id)
        return ArtifactDetail(**item.model_dump(), pages=[], redirect_chain=[], media=[Media(
            id=m["id"], kind=m["kind"] if m["kind"] in {"screenshot", "frame", "image"} else "image",
            frame_ts=m["frame_ts"], ocr_text=None, width=0, height=0) for m in media], ocr_text=None,
            request_count=0, hosts_display=[])
    if artifact_id != seed.ARTIFACT.id: raise HTTPException(404, "Artifact not found")
    return seed.ARTIFACT_DETAIL

@router.get("/media/{media_id}", responses={200: {"content": {"image/png": {}}}})
def media(media_id: str) -> Response:
    if repo := live.repository():
        row = repo.get_media(media_id)
        if not row: raise HTTPException(404, "Media not found")
        try: path = live.safe_media_path(row)
        except FileNotFoundError: raise HTTPException(404, "Media not found")
        return FileResponse(path)
    if media_id != "media_demo": raise HTTPException(404, "Media not found")
    return Response(b"\x89PNG\r\n\x1a\n", media_type="image/png")

@router.get("/campaigns", response_model=list[CampaignSummary])
def campaigns() -> list[CampaignSummary]:
    if repo := live.repository(): return [live.campaign(repo, row) for row in repo.list_campaigns()]
    return [seed.CAMPAIGN]

@router.get("/campaigns/{campaign_id}", response_model=CampaignDetail)
def campaign(campaign_id: str) -> CampaignDetail:
    if repo := live.repository():
        row = next((row for row in repo.list_campaigns() if row["id"] == campaign_id), None)
        if not row: raise HTTPException(404, "Campaign not found")
        item = live.campaign(repo, row)
        members = [live.incident(repo, repo.get_incident(i)) for i in item.incident_ids]
        edges = [live.edge(e) for e in repo.list_edges()
                 if e["a_incident"] in item.incident_ids and e["b_incident"] in item.incident_ids]
        return CampaignDetail(**item.model_dump(), members=members, edges=edges, timeline=[])
    if campaign_id != seed.CAMPAIGN.id: raise HTTPException(404, "Campaign not found")
    return CampaignDetail(**seed.CAMPAIGN.model_dump(), members=[seed.INCIDENT],
                          edges=[seed.EDGE], timeline=[])

@router.get("/campaigns/{campaign_id}/links", response_model=list[CampaignLink])
def campaign_links(campaign_id: str) -> list[CampaignLink]:
    if repo := live.repository():
        if campaign_id not in {row["id"] for row in repo.list_campaigns()}:
            raise HTTPException(404, "Campaign not found")
        return []
    if campaign_id != seed.CAMPAIGN.id: raise HTTPException(404, "Campaign not found")
    return []

@router.get("/graph", response_model=GraphResponse)
def graph(campaign: str | None = None, tiers: str | None = None,
          levels: str | None = None) -> GraphResponse:
    if repo := live.repository():
        items = [live.incident(repo, row) for row in repo.list_incidents()]
        if campaign: items = [item for item in items if item.campaign_id == campaign]
        edges = [live.edge(row) for row in repo.list_edges()]
        visible_ids = {item.id for item in items}
        edges = [edge for edge in edges if edge.source in visible_ids and edge.target in visible_ids
                 and (not tiers or edge.tier.value in tiers.split(","))
                 and (not levels or edge.level.value in levels.split(","))]
        return GraphResponse(nodes=[GraphNode(id=item.id, kind="incident", label=item.label,
            parent=item.campaign_id, outcome=item.outcome, coverage_level=item.coverage.level) for item in items], edges=edges)
    if campaign and campaign != seed.CAMPAIGN.id:
        return GraphResponse(nodes=[], edges=[])
    node = GraphNode(id=seed.INCIDENT.id, kind="incident", label=seed.INCIDENT.label,
                     parent=seed.CAMPAIGN.id, outcome=seed.INCIDENT.outcome, coverage_level="ok")
    edge = seed.EDGE
    visible = (not tiers or edge.tier in tiers.split(",")) and (not levels or edge.level in levels.split(","))
    return GraphResponse(nodes=[node], edges=[edge] if visible else [])

MULTIPART = {"requestBody": {"content": {"multipart/form-data": {"schema": {
    "type": "object", "properties": {"files": {"type": "array", "items": {"type": "string", "format": "binary"}},
    "text": {"type": "string"}, "url": {"type": "string"}, "exclude_incident": {"type": "string"}}}}}}}

@router.post("/classify", response_model=ClassifyResult, openapi_extra=MULTIPART)
async def classify(_request: Request) -> ClassifyResult:
    body = await _request.body()
    content_type = _request.headers.get("content-type", "")
    values = re.findall(rb'name="(?:files|text|url)"[^\r\n]*\r\n(?:[^\r\n]*\r\n)*\r\n(.*?)(?=\r\n--)', body, re.DOTALL)
    if not content_type.startswith("multipart/form-data") or not any(value.strip() for value in values):
        raise HTTPException(422, "At least one file, text, or URL is required")
    if repo := live.repository():
        excluded = re.search(rb'name="exclude_incident"[^\r\n]*\r\n\r\n(.*?)(?=\r\n--)', body, re.DOTALL)
        try: result, bundle, candidates = live.classify_multipart(repo, body, content_type,
            excluded.group(1).decode() if excluded else None)
        except OverflowError: raise HTTPException(413, "Upload exceeds the size limit")
        except ValueError: raise HTTPException(422, "Invalid multipart body")
        items = [EvidenceItem(id=f"candidate-{i}", type=e.type, tier=e.tier, family=e.family,
            display=e.display, weight=e.weight, artifact_id=e.artifact_id or "",
            funnel_step=e.funnel_step, ignored=e.ignored, ignore_reason=e.ignore_reason)
            for i, e in enumerate(bundle.evidence)]
        kind = "match" if result.outcome == "known_campaign" else "conflict" if result.outcome == "needs_review" else "weak"
        return ClassifyResult(outcome=result.outcome, campaign_id=result.campaign_id,
            campaign_label=result.campaign_id, reasons=[Reason(kind=kind, text=result.reasons[0], evidence=items)],
            coverage=live.coverage(__import__("json").dumps(bundle.coverage.to_dict())), evidence=items,
            candidate_edges=[Edge(id=f"candidate-{i}", source=e.source, target=e.target,
                level=e.level, tier=e.tier, families=list(e.families), score=e.score,
                comparable=e.comparable, low_confidence=e.low_confidence, evidence=[]) for i, e in enumerate(candidates)], elapsed_ms=0)
    reason = Reason(kind="match", text="Synthetic tier-A campaign match.", evidence=[seed.EVIDENCE])
    return ClassifyResult(outcome="known_campaign", campaign_id=seed.CAMPAIGN.id,
        campaign_label=seed.CAMPAIGN.label, reasons=[reason], coverage=seed.COVERAGE,
        evidence=[seed.EVIDENCE], candidate_edges=[seed.EDGE], elapsed_ms=1)

@router.get("/eval/report", response_model=EvalReport)
def evaluation() -> EvalReport:
    return EvalReport.model_validate(build_report())

@router.post("/edges/{edge_id}/decision", status_code=status.HTTP_501_NOT_IMPLEMENTED)
@router.post("/campaigns/merge", status_code=status.HTTP_501_NOT_IMPLEMENTED)
@router.post("/campaigns/split", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def optional_mutation() -> None: raise HTTPException(501, "Optional endpoint not enabled")

@router.get("/exports/{name}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def optional_export(name: str) -> None: raise HTTPException(501, "Optional exporter not enabled")
