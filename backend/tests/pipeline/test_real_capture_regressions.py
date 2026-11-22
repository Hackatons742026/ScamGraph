"""Regressions found by importing a real capture set (all fixtures here are synthetic)."""

from __future__ import annotations

import json
from pathlib import Path

from backend.db import Repository
from backend.pipeline.extract.extractors import extract_html, extract_text, extract_url
from backend.pipeline.extract.ignore import is_platform_domain
from backend.pipeline.extract.normalize import norm_domain_from_url
from backend.pipeline.intake.discover import discover_incidents
from backend.pipeline.intake.html import parse_html
from backend.pipeline.models import Artifact, ArtifactKind
from backend.pipeline.run import run_on_data_dir

SALT = "synthetic-regression-salt"


def _artifact(path: Path, kind: str = "html", step: int | None = None) -> Artifact:
    return Artifact(id=f"art-{path.stem}", incident_id="inc-synthetic", kind=kind, path=str(path),
                    funnel_step=step)


def _saved_page(folder: Path, body: str = "") -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    files = folder / "Synthetic Offer_files"
    files.mkdir(exist_ok=True)
    (files / "hero.png").write_bytes(b"synthetic-image-bytes")
    (files / "app.js").write_text("console.log('synthetic kit');", encoding="utf-8")
    page = folder / "Synthetic Offer.html"
    page.write_text(
        "<html><head><title>Synthetic Offer</title>"
        "<script src='Synthetic Offer_files/app.js'></script></head><body>"
        "<img src='Synthetic Offer_files/hero.png'>"
        "<a href='delivered'>relative</a><a href='//cdn.offer-synthetic.test/x'>cdn</a>"
        "<a href='https://www.facebook.com/sharer'>share</a>"
        f"<form action='order.php'><input name='phone'></form>{body}</body></html>",
        encoding="utf-8",
    )
    return page


def test_domains_require_a_dotted_host_and_web_scheme() -> None:
    assert norm_domain_from_url("https://www.offer.example-synthetic.test/x") == "offer.example-synthetic.test"
    assert norm_domain_from_url("http://delivered") is None
    assert norm_domain_from_url("file:///data/case/delivered") is None
    assert norm_domain_from_url("https://203.0.113.10/") is None


def test_platform_domains_are_recognised_with_subdomains() -> None:
    assert is_platform_domain("facebook.com") and is_platform_domain("apps.apple.com")
    assert is_platform_domain("www.google.com")
    assert not is_platform_domain("offer.example-synthetic.test")
    assert not is_platform_domain("notfacebook.com")


def test_saved_page_evidence_never_contains_local_paths(tmp_path: Path) -> None:
    page = _saved_page(tmp_path / "private-case-folder")
    html = parse_html(page, salt=SALT)
    evidence = extract_html(_artifact(page), html, salt=SALT)

    rendered = json.dumps([e.display for e in evidence] + html.links + [str(a) for a in html.assets])
    assert str(tmp_path) not in rendered and "private-case-folder" not in rendered
    assert "file:" not in json.dumps([e.display for e in evidence])
    displays = {e.type: e.display for e in evidence if e.type in {"js_hash", "content_image"}}
    assert displays == {"js_hash": "local:app.js", "content_image": "local:hero.png"}
    domains = {e.display: e for e in evidence if e.type == "landing_domain"}
    assert "delivered" not in domains
    assert "cdn.offer-synthetic.test" in domains
    assert domains["facebook.com"].ignored and domains["facebook.com"].ignore_reason == "platform_domain"
    orders = [e.display for e in evidence if e.type == "order_endpoint"]
    assert orders == ["/order.php"]


def test_local_assets_match_by_content_across_incident_folders(tmp_path: Path) -> None:
    first = _saved_page(tmp_path / "case-one")
    second = _saved_page(tmp_path / "case-two")
    hashes = []
    for page in (first, second):
        evidence = extract_html(_artifact(page), parse_html(page, salt=SALT), salt=SALT)
        hashes.append({e.type: e.value_hash for e in evidence if e.type in {"js_hash", "content_image"}})
    assert hashes[0] == hashes[1]


def test_telegram_handles_are_masked_and_emails_are_not_handles(tmp_path: Path) -> None:
    page = _saved_page(tmp_path / "case", body=(
        "<p>Write to support.team@gmail.com or join t.me/SyntheticChannel88 today.</p>"
        "<p>Short @abc is not a handle.</p>"))
    evidence = extract_html(_artifact(page), parse_html(page, salt=SALT), salt=SALT)
    handles = [e.display for e in evidence if e.type == "telegram"]
    assert handles == ["@Sy…88"]


def test_pasted_text_and_urls_produce_evidence() -> None:
    art = Artifact(id="art-text", incident_id="inc", kind=ArtifactKind.TEXT, path="note.txt")
    text = extract_text(art, "Zadzwoń +48 500 600 700 lub wejdź na https://offer.example-synthetic.test/start "
                             "albo t.me/SyntheticChannel88.", salt=SALT)
    kinds = {e.type for e in text}
    assert {"phone", "telegram", "landing_domain"} <= kinds
    url_art = Artifact(id="art-url", incident_id="inc", kind=ArtifactKind.URL, path="url.txt")
    url = extract_url(url_art, "go.example-synthetic.test/click?clickid=SYNTH&sub=1", salt=SALT)
    assert {(e.type, e.display) for e in url} >= {("click_domain", "go.example-synthetic.test")}
    assert any(e.type == "url_param_set" and e.display == "clickid,sub" for e in url)


def test_discovery_finds_nested_bundles_and_adlib_json_by_content(tmp_path: Path) -> None:
    case = tmp_path / "data" / "case"
    bundle = case / "export" / "export"
    bundle.mkdir(parents=True)
    (bundle / "manifest.json").write_text(json.dumps({"url": "https://offer.example-synthetic.test/"}))
    (bundle / "page.har").write_text(json.dumps({"log": {"entries": []}}))
    (case / "Ad 123.json").write_text(json.dumps({"extractor": "facebook:ads", "ad_id": "SYNTH1"}))
    (case / "notes.json").write_text(json.dumps({"unrelated": True}))

    incident = discover_incidents(tmp_path / "data")[0]
    kinds = sorted(a.kind.value for a in incident.artifacts)
    assert kinds == ["adlib_json", "bundle"]


def test_import_records_capture_time_requests_and_redirects(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SCAMGRAPH_SALT", SALT)
    monkeypatch.setenv("SCAMGRAPH_CACHE_DIR", str(tmp_path / "cache"))
    case = tmp_path / "data" / "case"
    case.mkdir(parents=True)
    har = {"log": {"entries": [
        {"startedDateTime": "2026-03-04T10:00:05.000+01:00",
         "request": {"method": "GET", "url": "https://go.example-synthetic.test/click?clickid=SYNTH", "headers": []},
         "response": {"status": 302, "headers": [{"name": "Location",
                      "value": "https://offer.example-synthetic.test/landing"}], "content": {"mimeType": "text/html"}}},
        {"startedDateTime": "2026-03-04T10:00:06.000+01:00",
         "request": {"method": "GET", "url": "https://offer.example-synthetic.test/landing", "headers": []},
         "response": {"status": 200, "headers": [], "content": {"mimeType": "text/html", "text": "<html></html>"}}},
    ]}}
    (case / "capture.har").write_text(json.dumps(har))
    db = tmp_path / "live.db"

    run_on_data_dir(tmp_path / "data", db_path=db)

    repo = Repository(db)
    incident = repo.list_incidents()[0]
    assert incident["first_seen"].startswith("2026-03-04T09:00:05")
    artifact = repo.get_artifacts(incident["id"])[0]
    assert artifact["captured_at"].startswith("2026-03-04T09:00:05")
    detail = repo.artifact_details([artifact["id"]])[artifact["id"]]
    assert detail["request_count"] == 2
    assert detail["hosts"] == ["go.example-synthetic.test", "offer.example-synthetic.test"]
    assert [(h["seq"], h["kind"], h["status"]) for h in detail["redirects"]] == [(1, "3xx", 302)]
    assert detail["pages"][0]["domain"] == "offer.example-synthetic.test"

    # Re-import replaces rows instead of duplicating them.
    run_on_data_dir(tmp_path / "data", db_path=db)
    assert repo.artifact_details([artifact["id"]])[artifact["id"]]["request_count"] == 2


def test_har_hosts_without_a_domain_never_become_domain_evidence(tmp_path: Path) -> None:
    from backend.pipeline.extract.extractors import extract_har
    from backend.pipeline.intake.har import parse_har

    capture = tmp_path / "capture.har"
    capture.write_text(json.dumps({"log": {"entries": [
        {"request": {"method": "GET", "url": "https://delivered/pixel", "headers": []},
         "response": {"status": 200, "headers": [], "content": {"mimeType": "image/gif"}}},
        {"request": {"method": "GET", "url": "https://offer.example-synthetic.test/", "headers": []},
         "response": {"status": 200, "headers": [], "content": {"mimeType": "text/html"}}},
    ]}}))
    evidence = extract_har(_artifact(capture, "har"), parse_har(capture, salt=SALT), salt=SALT)
    assert {e.display for e in evidence if e.type == "landing_domain"} == {"offer.example-synthetic.test"}


def test_unsaved_relative_assets_show_only_a_file_name(tmp_path: Path) -> None:
    page = tmp_path / "bundle" / "dom.html"
    page.parent.mkdir()
    page.write_text("<html><head><script src='resources/js/kit.min.js'></script></head><body>x</body></html>")
    evidence = extract_html(_artifact(page), parse_html(page, salt=SALT), salt=SALT)
    assert [e.display for e in evidence if e.type == "js_hash"] == ["local:kit.min.js"]


def test_capture_bundle_counts_as_having_a_har() -> None:
    from backend.pipeline.extract import coverage_for

    artifacts = [Artifact(id="b", incident_id="i", kind=ArtifactKind.BUNDLE, path="bundle"),
                 Artifact(id="v", incident_id="i", kind=ArtifactKind.VIDEO, path="v.mp4")]
    assert "no HAR" not in coverage_for(artifacts, []).notes


def test_adlib_capture_time_falls_back_to_download_epoch(tmp_path: Path) -> None:
    from backend.pipeline.intake.adlib import parse_adlib

    path = tmp_path / "ad.info.json"
    path.write_text(json.dumps({"extractor": "facebook:ads", "id": "SYNTH1", "epoch": 1767225600}))
    assert parse_adlib(path, salt=SALT).captured_at == "2026-01-01T00:00:00+00:00"


def test_reimport_replaces_evidence_from_older_runs(tmp_path: Path, monkeypatch) -> None:
    from backend.pipeline.models import Evidence

    monkeypatch.setenv("SCAMGRAPH_SALT", SALT)
    monkeypatch.setenv("SCAMGRAPH_CACHE_DIR", str(tmp_path / "cache"))
    _saved_page(tmp_path / "data" / "case")
    db = tmp_path / "live.db"
    run_on_data_dir(tmp_path / "data", db_path=db)
    repo = Repository(db)
    incident_id = repo.list_incidents()[0]["id"]
    stale = Evidence("js_hash", "B", "kit", "old-path-hash", "file:///data/case/old.js", 1.0, None, None)
    repo.save_evidence(incident_id, [stale])

    run_on_data_dir(tmp_path / "data", db_path=db)

    displays = [row["display_value"] for row in repo.get_evidence(incident_id)]
    assert "file:///data/case/old.js" not in displays and "local:app.js" in displays


def test_funnel_page_is_never_an_embedded_widget(tmp_path: Path) -> None:
    from backend.pipeline.intake.har import parse_har
    from backend.pipeline.run import _artifact_details

    capture = tmp_path / "widgets.har"
    capture.write_text(json.dumps({"log": {"entries": [
        {"request": {"method": "GET", "url": "https://www.googletagmanager.com/ns.html?id=GTM-SYNTH", "headers": []},
         "response": {"status": 200, "headers": [], "content": {"mimeType": "text/html"}}},
    ]}}))
    art = _artifact(capture, "har")
    _, _, pages = _artifact_details([art], {art.id: parse_har(capture, salt=SALT)}, {})
    assert pages[0]["domain"] is None
