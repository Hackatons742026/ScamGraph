"""Contract-v1 endpoints backed by synthetic seed objects."""

import re

from fastapi import APIRouter, HTTPException, Request, Response, status

from . import seed
from .schemas import *  # noqa: F403
from backend.eval import build_report

ERRORS = {code: {"model": ErrorResponse} for code in (404, 413, 422, 501)}
router = APIRouter(prefix="/api", responses=ERRORS)

@router.post("/import", response_model=ImportAccepted, status_code=202)
def start_import(_request: ImportRequest | None = None) -> ImportAccepted:
    return ImportAccepted(run_id=seed.RUN.id)

@router.get("/runs/latest", response_model=RunSummary)
def latest_run() -> RunSummary:
    return seed.RUN

@router.get("/runs/{run_id}", response_model=RunSummary)
def get_run(run_id: str) -> RunSummary:
    if run_id != seed.RUN.id: raise HTTPException(404, "Run not found")
    return seed.RUN

@router.get("/incidents", response_model=list[IncidentSummary])
def incidents(status: str | None = None, campaign: str | None = None) -> list[IncidentSummary]:
    item = seed.INCIDENT
    return [item] if (not status or item.status in status.split(",")) and (not campaign or item.campaign_id == campaign) else []

@router.get("/incidents/{incident_id}", response_model=IncidentDetail)
def incident(incident_id: str) -> IncidentDetail:
    if incident_id != seed.INCIDENT.id: raise HTTPException(404, "Incident not found")
    return seed.INCIDENT_DETAIL

@router.get("/artifacts/{artifact_id}", response_model=ArtifactDetail)
def artifact(artifact_id: str) -> ArtifactDetail:
    if artifact_id != seed.ARTIFACT.id: raise HTTPException(404, "Artifact not found")
    return seed.ARTIFACT_DETAIL

@router.get("/media/{media_id}", responses={200: {"content": {"image/png": {}}}})
def media(media_id: str) -> Response:
    if media_id != "media_demo": raise HTTPException(404, "Media not found")
    return Response(b"\x89PNG\r\n\x1a\n", media_type="image/png")

@router.get("/campaigns", response_model=list[CampaignSummary])
def campaigns() -> list[CampaignSummary]: return [seed.CAMPAIGN]

@router.get("/campaigns/{campaign_id}", response_model=CampaignDetail)
def campaign(campaign_id: str) -> CampaignDetail:
    if campaign_id != seed.CAMPAIGN.id: raise HTTPException(404, "Campaign not found")
    return CampaignDetail(**seed.CAMPAIGN.model_dump(), members=[seed.INCIDENT],
                          edges=[seed.EDGE], timeline=[])

@router.get("/campaigns/{campaign_id}/links", response_model=list[CampaignLink])
def campaign_links(campaign_id: str) -> list[CampaignLink]:
    if campaign_id != seed.CAMPAIGN.id: raise HTTPException(404, "Campaign not found")
    return []

@router.get("/graph", response_model=GraphResponse)
def graph(campaign: str | None = None, tiers: str | None = None,
          levels: str | None = None) -> GraphResponse:
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
