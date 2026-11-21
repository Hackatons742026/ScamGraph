import pytest
from fastapi.testclient import TestClient

from backend.api.main import app

client = TestClient(app)


def contract_error(response, code, error):
    assert response.status_code == code
    assert response.json()["error"] == error
    assert isinstance(response.json()["detail"], str) and response.json()["detail"]


@pytest.mark.parametrize("path", [
    "/api/runs/latest", "/api/runs/run_demo", "/api/incidents",
    "/api/incidents/inc_demo", "/api/artifacts/art_demo", "/api/campaigns",
    "/api/campaigns/camp_demo", "/api/campaigns/camp_demo/links", "/api/graph",
    "/api/eval/report",
])
def test_read_endpoints_are_valid_masked_and_deterministic(path):
    response = client.get(path)
    assert response.status_code == 200 and "value_hash" not in response.text
    assert client.get(path).json() == response.json()


def test_filters_route_ordering_and_report_shape():
    assert client.get("/api/runs/latest").json() == client.get("/api/runs/run_demo").json()
    assert len(client.get("/api/incidents?status=in_campaign,unassigned&campaign=camp_demo").json()) == 1
    assert client.get("/api/incidents?status=needs_review").json() == []
    assert client.get("/api/graph?tiers=B&levels=network").json()["edges"] == []
    report = client.get("/api/eval/report").json()
    assert set(report) == {"generated_at", "scenarios", "pairs", "false_merges", "loo", "ablation"}
    assert set(report["pairs"]) == {"n_pairs", "mentor_verified", "agreement", "campaign", "network"}


def test_mutations_media_and_contract_errors():
    assert client.post("/api/import", json={}).json() == {"run_id": "run_demo"}
    classified = client.post("/api/classify", files={"text": (None, "synthetic")})
    assert classified.json()["outcome"] == "known_campaign" and "value_hash" not in classified.text
    media = client.get("/api/media/media_demo")
    assert media.headers["content-type"] == "image/png" and media.content.startswith(b"\x89PNG")
    contract_error(client.post("/api/classify"), 422, "validation_error")
    contract_error(client.post("/api/import", json={"path": 42}), 422, "validation_error")
    for path in ("/api/runs/missing", "/api/incidents/missing", "/api/artifacts/missing",
                 "/api/campaigns/missing", "/api/media/missing"):
        contract_error(client.get(path), 404, "not_found")
    for method, path in (("post", "/api/edges/x/decision"), ("post", "/api/campaigns/merge"),
                         ("post", "/api/campaigns/split"), ("get", "/api/exports/report")):
        contract_error(getattr(client, method)(path), 501, "http_error")


def test_openapi_paths_named_components_and_multipart():
    schema = client.get("/openapi.json").json()
    paths = {"/api/import", "/api/runs/latest", "/api/runs/{run_id}", "/api/incidents",
        "/api/incidents/{incident_id}", "/api/artifacts/{artifact_id}", "/api/media/{media_id}",
        "/api/campaigns", "/api/campaigns/{campaign_id}", "/api/campaigns/{campaign_id}/links",
        "/api/graph", "/api/classify", "/api/eval/report", "/api/edges/{edge_id}/decision",
        "/api/campaigns/merge", "/api/campaigns/split", "/api/exports/{name}"}
    components = {"Tier", "Family", "Level", "Outcome", "IncidentStatus", "ArtifactKind",
        "ParseStatus", "FunnelRole", "CoverageLevel", "RunStatus", "ReasonKind", "EvidenceItem",
        "IncidentSummary", "IncidentDetail", "CampaignSummary", "CampaignDetail", "ClassifyResult",
        "EvalReport", "ErrorResponse"}
    assert paths <= set(schema["paths"]) and components <= set(schema["components"]["schemas"])
    assert "application/json" in schema["paths"]["/api/import"]["post"]["requestBody"]["content"]
    multipart = schema["paths"]["/api/classify"]["post"]["requestBody"]["content"]
    assert multipart["multipart/form-data"]["schema"]["properties"]["files"]["items"]["format"] == "binary"
