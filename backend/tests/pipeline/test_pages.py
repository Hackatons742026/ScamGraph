"""HTML / MHTML / capture-bundle parser tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.pipeline.intake.bundle import parse_bundle
from backend.pipeline.intake.html import parse_html
from backend.pipeline.intake.mhtml import parse_mhtml
from backend.pipeline.models import ParseStatus
from backend.pipeline.redact import hash_secret
from backend.tests.fixtures.synthetic_pages import (
    write_bundle,
    write_mhtml,
    write_saved_page,
    write_small_page,
)


@pytest.fixture(autouse=True)
def _salt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCAMGRAPH_SALT", "unit-test-salt")


def test_html_extracts_title_links_forms_and_assets(tmp_path: Path) -> None:
    path = write_saved_page(tmp_path / "page")
    result = parse_html(path)
    assert result.parse_status == ParseStatus.OK
    assert result.title == "Synthetic Offer"
    assert "Offer" in result.visible_text
    assert result.files_dir
    assert any("fbclid=" in link for link in result.links)
    assert all("SYNTHFB99" not in link for link in result.links)
    assert hash_secret("SYNTHFB99") in " ".join(result.links)
    assert result.forms
    assert result.forms[0].field_names == ["phone", "email"]
    assert "SYNTHTOK99" not in (result.forms[0].action_redacted or "")
    scripts = [a for a in result.assets if a.kind == "script"]
    assert any(a.is_library for a in scripts)
    assert any(a.local and not a.is_library for a in scripts)
    images = [a for a in result.assets if a.kind == "image"]
    assert images and images[0].local
    assert result.dom_skeleton
    assert result.dom_skeleton_sha256
    assert result.main_bytes >= 5 * 1024


def test_small_html_skips_dom_skeleton(tmp_path: Path) -> None:
    result = parse_html(write_small_page(tmp_path / "tiny"))
    assert result.parse_status == ParseStatus.OK
    assert result.dom_skeleton is None
    assert result.main_bytes < 5 * 1024


def test_mhtml_splits_and_parses_html_part(tmp_path: Path) -> None:
    path = write_mhtml(tmp_path / "saved.mhtml")
    result = parse_mhtml(path)
    assert result.parse_status == ParseStatus.OK
    assert result.part_count >= 2
    assert result.html is not None
    assert result.html.title == "MHTML Page"
    assert all("SYNTHGCL01" not in link for link in result.html.links)


def test_bundle_reads_manifest_dom_har_resources(tmp_path: Path) -> None:
    root = write_bundle(tmp_path / "capture_bundle")
    result = parse_bundle(root)
    assert result.parse_status in {ParseStatus.OK, ParseStatus.PARTIAL}
    assert result.captured_at == "2026-01-02T03:04:05Z"
    assert result.url_redacted
    assert "SYNTHFB77" not in result.url_redacted
    assert "keep=1" in result.url_redacted
    assert result.html is not None
    assert result.html.title == "Bundle DOM"
    assert result.har is not None
    assert result.har.requests
    assert result.resource_count == 2
    assert "nested/b.js" in result.resource_names


def test_broken_html_and_bundle_do_not_crash(tmp_path: Path) -> None:
    missing = parse_html(tmp_path / "nope.html")
    assert missing.parse_status == ParseStatus.FAILED
    empty = tmp_path / "empty_bundle"
    empty.mkdir()
    bad = parse_bundle(empty)
    assert bad.parse_status == ParseStatus.FAILED
    assert bad.error
