"""API regressions found with a real capture set; every fixture here is synthetic."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import live
from backend.api.main import app
from backend.db import Repository
from backend.pipeline.models import Artifact, Coverage, Evidence, Incident

client = TestClient(app)


def _har(*entries: dict) -> str:
    return json.dumps({"log": {"entries": list(entries)}})


def _entry(url: str, status: int, *, location: str | None = None) -> dict:
    headers = [{"name": "Location", "value": location}] if location else []
    return {"startedDateTime": "2026-02-01T08:00:00Z",
            "request": {"method": "GET", "url": url, "headers": []},
            "response": {"status": status, "headers": headers,
                         "content": {"mimeType": "text/html", "text": "<html></html>"}}}


@pytest.fixture
def imported(tmp_path, monkeypatch):
    """A funnel incident imported through POST /api/import."""
    pil = pytest.importorskip("PIL.Image")
    data = tmp_path / "data"
    case = data / "case-funnel"
    (case / "strona_1").mkdir(parents=True)
    (case / "strona_2").mkdir()
    (case / "strona_1" / "capture.har").write_text(_har(
        _entry("https://www.googletagmanager.com/ns.html?id=GTM-SYNTH", 200),  # embedded iframe, not the page
        _entry("https://go.example-synthetic.test/click?clickid=SYNTH", 302,
               location="https://offer.example-synthetic.test/start"),
        _entry("https://offer.example-synthetic.test/start", 200)))
    (case / "strona_2" / "offer.html").write_text(
        "<html><head><title>Synthetic offer</title></head><body><p>Cena 99 zł</p></body></html>")
    pil.new("RGB", (32, 16), "white").save(case / "ad.png")
    (case / "clip.mp4").write_bytes(b"not a real video")
    for key, value in {"SCAMGRAPH_DB": tmp_path / "live.db", "SCAMGRAPH_DATA_DIR": data,
                       "SCAMGRAPH_CACHE_DIR": tmp_path / "cache"}.items():
        monkeypatch.setenv(key, str(value))
    monkeypatch.setenv("SCAMGRAPH_SALT", "synthetic-api-salt")
    monkeypatch.setenv("SCAMGRAPH_ASR", "0")
    accepted = client.post("/api/import", json={})
    assert accepted.status_code == 202
    run = client.get(f"/api/runs/{accepted.json()['run_id']}").json()
    assert run["status"] == "done"
    return run, tmp_path


def test_import_exposes_funnel_redirects_requests_and_media_size(imported, monkeypatch) -> None:
    run, tmp_path = imported
    incident = client.get("/api/incidents").json()[0]
    detail = client.get(f"/api/incidents/{incident['id']}").json()

    steps = {step["step"]: step for step in detail["funnel"]}
    assert sorted(steps) == [1, 2]
    assert steps[1]["domain_display"] == "offer.example-synthetic.test"
    assert [hop["kind"] for hop in steps[1]["redirect_chain"]] == ["3xx"]
    assert steps[2]["role"] == "offer"

    names = {a["kind"]: a["name_display"] for a in detail["artifacts"]}
    assert names["har"] == "capture.har" and names["image"] == "ad.png"
    assert str(tmp_path) not in json.dumps(detail)

    har = next(a for a in detail["artifacts"] if a["kind"] == "har")
    har_detail = client.get(f"/api/artifacts/{har['id']}").json()
    assert har_detail["request_count"] == 3
    assert har_detail["hosts_display"] == [
        "go.example-synthetic.test", "offer.example-synthetic.test", "www.googletagmanager.com"]
    assert har_detail["redirect_chain"][0]["status"] == 302
    assert har_detail["pages"][0]["domain_display"] == "offer.example-synthetic.test"

    image = next(a for a in detail["artifacts"] if a["kind"] == "image")
    media = client.get(f"/api/artifacts/{image['id']}").json()["media"]
    assert (media[0]["width"], media[0]["height"]) == (32, 16)

    video = next(a for a in detail["artifacts"] if a["kind"] == "video")
    assert video["parse_status"] == "partial"
    expected = ("Video frames could not be extracted" if shutil.which("ffmpeg")
                else "ffmpeg is not installed")
    assert expected in video["error"]
    assert run["artifacts_by_kind"]["video"] == {"total": 1, "parsed": 1, "failed": 0, "partial": 1}
    assert detail["first_seen"].startswith("2026-02-01T08:00:00")


def test_video_and_capture_errors_are_actionable() -> None:
    assert live.safe_artifact_error("video", "partial", "ffmpeg failed: /private/x.mp4").startswith(
        "Video frames could not be extracted")
    assert live.safe_artifact_error("har", "failed", "JSONDecodeError at /data/x").startswith(
        "Capture could not be parsed")
    assert live.safe_artifact_error("adlib_json", "partial", "no ad_id/page_id fields") == \
        "Ad Library JSON has no ad or advertiser page ID."


def _evidence_backed_repo(db_path: Path) -> Repository:
    repo = Repository(db_path)
    for identifier in ("inc-a", "inc-b", "inc-c", "inc-d", *(f"inc-bg-{n}" for n in range(4))):
        repo.save_incident(Incident(identifier, "synthetic", title=identifier,
                                    coverage=Coverage(kinds_present=["har"], notes=[])))
    shared = {
        "inc-a": [("pixel_id", "A", None, "px-ab")],
        "inc-b": [("pixel_id", "A", None, "px-ab"), ("kit_hash", "B", "kit", "kit-bc")],
        "inc-c": [("click_domain", "B", "tds", "tds-cd"), ("landing_domain", "B", "domain", "dom-cd"),
                  ("kit_hash", "B", "kit", "kit-bc")],
        "inc-d": [("click_domain", "B", "tds", "tds-cd"), ("landing_domain", "B", "domain", "dom-cd")],
    }
    for identifier, rows in shared.items():
        repo.save_artifacts([Artifact(f"art-{identifier}", identifier, "har", "synthetic.har", parse_status="ok")])
        repo.save_evidence(identifier, [Evidence(kind, tier, family, value, f"{kind}-****", 1.0,
                                                 f"art-{identifier}", 1) for kind, tier, family, value in rows])
    edges, groups, decisions, _ = live.analysis_snapshot(repo)
    repo.save_analysis(edges, groups, decisions)
    return repo


def _rebuild(repo: Repository) -> None:
    edges, groups, decisions, _ = live.analysis_snapshot(repo)
    repo.save_analysis(edges, groups, decisions)


def test_campaign_members_have_matching_decisions_and_related_groups(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SCAMGRAPH_DB", str(tmp_path / "groups.db"))
    _evidence_backed_repo(tmp_path / "groups.db")

    incidents = {i["id"]: i for i in client.get("/api/incidents").json()}
    for identifier in ("inc-a", "inc-b", "inc-c", "inc-d"):
        assert incidents[identifier]["status"] == "in_campaign"
        assert incidents[identifier]["outcome"] == "known_campaign"
        assert incidents[identifier]["reason_summary"].startswith("Grouped with 1 other incident")
    campaign_a = incidents["inc-a"]["campaign_id"]
    campaign_c = incidents["inc-c"]["campaign_id"]

    links = client.get(f"/api/campaigns/{campaign_a}/links").json()
    assert [(link["other_id"], link["level"]) for link in links] == [(campaign_c, "campaign")]
    assert links[0]["shared_evidence"][0]["type"] == "kit_hash"


def test_merge_replay_keeps_networks_and_labels_stay_stable(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SCAMGRAPH_DB", str(tmp_path / "labels.db"))
    repo = _evidence_backed_repo(tmp_path / "labels.db")
    before = {c["id"]: c["label"] for c in client.get("/api/campaigns").json()}
    campaign_a = client.get("/api/incidents/inc-a").json()["campaign_id"]
    campaign_c = client.get("/api/incidents/inc-c").json()["campaign_id"]

    merged = client.post("/api/campaigns/merge", json={"campaign_ids": [campaign_a, campaign_c]})
    assert merged.status_code == 200 and merged.json()["size"] == 4
    _rebuild(repo)  # e.g. a later upload re-runs the analysis and replays the merge

    campaigns = {c["id"]: c for c in client.get("/api/campaigns").json()}
    assert campaigns[campaign_a]["size"] == 4 and campaigns[campaign_a]["label"] == before[campaign_a]
    networks = [c for c in campaigns.values() if c["level"] == "network"]
    assert networks and all(n["size"] >= 2 for n in networks)
    assert campaigns[campaign_a]["network_id"] == networks[0]["id"]

    split = client.post("/api/campaigns/split", json={"campaign_id": campaign_a, "incident_ids": ["inc-d"]})
    assert split.status_code == 200
    labels = {c["id"]: c["label"] for c in client.get("/api/campaigns").json()}
    assert labels[campaign_a] == before[campaign_a]
    assert labels[split.json()[1]["id"]] not in before.values()  # numbers are never reused


def test_override_errors_have_plain_messages(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SCAMGRAPH_DB", str(tmp_path / "errors.db"))
    _evidence_backed_repo(tmp_path / "errors.db")
    campaign_a = client.get("/api/incidents/inc-a").json()["campaign_id"]
    response = client.post("/api/campaigns/merge", json={"campaign_ids": [campaign_a, "campaign-missing"]})
    assert response.status_code == 404 and response.json()["detail"] == "Campaign not found"


def test_leave_one_out_hides_links_and_unreadable_uploads_are_reported(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SCAMGRAPH_DB", str(tmp_path / "loo.db"))
    monkeypatch.setenv("SCAMGRAPH_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SCAMGRAPH_SALT", "synthetic-loo-salt")
    repo = Repository(tmp_path / "loo.db")
    for index in range(6):
        repo.save_incident(Incident(f"synthetic-background-{index}", "synthetic", coverage=Coverage()))
    page = ("<html><head><title>Offer</title></head><body><p>Join t.me/SyntheticChannel88 now.</p>"
            "</body></html>").encode()
    first = client.post("/api/classify", files={"files": ("offer-a.html", page, "text/html")})
    stored_id = next(i["id"] for i in client.get("/api/incidents").json() if i["id"].startswith("inc_"))

    loo = client.post("/api/classify", files={"files": ("offer-b.html", page, "text/html"),
                                              "exclude_incident": (None, stored_id)})
    assert first.status_code == loo.status_code == 200
    assert all(stored_id not in {e["source"], e["target"]} for e in loo.json()["candidate_edges"])

    broken = client.post("/api/classify", files={"files": ("broken.har", b"{not-json", "application/json")})
    notes = [r["text"] for r in broken.json()["reasons"] if r["kind"] == "coverage"]
    assert notes == ["broken.har: Capture could not be parsed. Export it again as a valid HAR (JSON) file."]


def test_funnel_lists_only_first_party_redirect_hops() -> None:
    from backend.api.schemas import ArtifactSummary

    art = ArtifactSummary(id="a", kind="har", name_display="capture.har", funnel_step=1, role="ad",
                          parse_status="ok", error=None, captured_at=None, duplicate_of=None, observations=1)
    details = {"a": {"pages": [], "redirects": [
        {"seq": 1, "url_display": "https://www.google.com/pagead/1p-conversion/1/?x=1", "status": 302, "kind": "3xx"},
        {"seq": 2, "url_display": "https://offer.example-synthetic.test/next", "status": 302, "kind": "3xx"},
    ]}}
    steps = live.funnel([art], details)
    assert [hop.url_display for hop in steps[0].redirect_chain] == ["https://offer.example-synthetic.test/next"]
