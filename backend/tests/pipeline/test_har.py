"""HAR parser tests — synthetic fixtures written to tmp (no committed .har files)."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.pipeline.intake.har import parse_har
from backend.pipeline.models import ParseStatus
from backend.pipeline.redact import hash_secret
from backend.tests.fixtures.synthetic_har import (
    build_broken_har_text,
    build_rich_har,
    write_har,
)


@pytest.fixture(autouse=True)
def _salt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCAMGRAPH_SALT", "unit-test-salt")


def test_parse_rich_har_ordered_requests_and_hosts(tmp_path: Path) -> None:
    path = write_har(tmp_path / "rich.json", build_rich_har())
    # Use a non-.har suffix in tmp to avoid accidental commits; parser is extension-agnostic.
    result = parse_har(path)
    assert result.parse_status == ParseStatus.OK
    assert result.error is None
    assert [r.seq for r in result.requests] == [0, 1, 2, 3]
    assert result.requests[0].method == "GET"
    assert result.requests[3].method == "POST"
    assert result.requests[3].is_post is True
    assert "ads.example-scam.test" in result.hosts
    assert "203.0.113.10" in result.server_ips
    assert any("/api/v1/order/{id}" in ep for ep in result.post_endpoints)


def test_redirect_chain_3xx_meta_and_js(tmp_path: Path) -> None:
    result = parse_har(write_har(tmp_path / "rich.json"))
    kinds = [h.kind for h in result.redirect_chain]
    assert "3xx" in kinds
    assert "meta" in kinds
    assert "js" in kinds
    for hop in result.redirect_chain:
        assert "SYNTHFB01" not in hop.url_display
        assert "SYNTHPXL01" not in hop.url_display


def test_secrets_redacted_from_stored_urls(tmp_path: Path) -> None:
    result = parse_har(write_har(tmp_path / "rich.json"))
    blob = " ".join(r.url_redacted for r in result.requests)
    for raw in (
        "SYNTHCLICK01",
        "SYNTHFB01",
        "SYNTHTOKEN01",
    ):
        assert raw not in blob
    assert hash_secret("SYNTHCLICK01") in blob


def test_tracking_ids_from_url_and_body(tmp_path: Path) -> None:
    result = parse_har(write_har(tmp_path / "rich.json"))
    kinds = {t.kind for t in result.tracking_ids}
    assert "meta_pixel" in kinds
    assert "pxl" in kinds or "meta_pixel" in kinds
    assert "aw_id" in kinds
    assert "gtm_id" in kinds
    assert "g_id" in kinds
    for hit in result.tracking_ids:
        assert len(hit.value_hash) == 12
        assert "SYNTH" not in hit.value_hash


def test_broken_har_returns_failed_without_crash(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text(build_broken_har_text(), encoding="utf-8")
    result = parse_har(path)
    assert result.parse_status == ParseStatus.FAILED
    assert result.error
    assert result.requests == []


def test_missing_salt_surfaces_as_failed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SCAMGRAPH_SALT", raising=False)
    result = parse_har(write_har(tmp_path / "rich.json"))
    assert result.parse_status == ParseStatus.FAILED
    assert result.error
    assert "SCAMGRAPH_SALT" in result.error
