"""Dedup + evidence extraction tests (synthetic only)."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.pipeline.dedup import dedupe_artifacts
from backend.pipeline.extract import ExtractInput, extract_all
from backend.pipeline.extract.ignore import ignore_reason_for
from backend.pipeline.intake.adlib import parse_adlib
from backend.pipeline.intake.har import parse_har
from backend.pipeline.intake.html import parse_html
from backend.pipeline.models import Artifact, ArtifactKind, EvidenceFamily, EvidenceTier
from backend.tests.fixtures.synthetic_har import write_har
from backend.tests.fixtures.synthetic_media import write_adlib
from backend.tests.fixtures.synthetic_pages import write_saved_page


@pytest.fixture(autouse=True)
def _salt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCAMGRAPH_SALT", "unit-test-salt")


def test_ignore_cdn_public_lib_placeholder() -> None:
    assert ignore_reason_for(evidence_type="server_ip", display="x", ip="104.16.1.1") == "cdn_ip"
    assert (
        ignore_reason_for(
            evidence_type="landing_domain",
            display="cdn.jsdelivr.net",
            host="cdn.jsdelivr.net",
        )
        == "public_lib"
    )
    assert (
        ignore_reason_for(evidence_type="phone", display="111111111", value="111111111")
        == "placeholder_phone"
    )
    assert (
        ignore_reason_for(
            evidence_type="dom_skeleton",
            display="x",
            doc_bytes=100,
        )
        == "small_doc"
    )


def test_dedupe_collapses_exact_and_links_variants(tmp_path: Path) -> None:
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    c = tmp_path / "copy.bin"
    v1 = tmp_path / "shot.png"
    v2 = tmp_path / "other" / "shot.png"
    v2.parent.mkdir()
    a.write_bytes(b"same-bytes")
    b.write_bytes(b"other-bytes")
    c.write_bytes(b"same-bytes")
    v1.write_bytes(b"variant-one")
    v2.write_bytes(b"variant-two")
    arts = [
        Artifact(id="1", incident_id="i", kind=ArtifactKind.IMAGE, path=str(a)),
        Artifact(id="2", incident_id="i", kind=ArtifactKind.IMAGE, path=str(c)),
        Artifact(id="3", incident_id="i", kind=ArtifactKind.IMAGE, path=str(b)),
        Artifact(id="4", incident_id="i", kind=ArtifactKind.IMAGE, path=str(v1)),
        Artifact(id="5", incident_id="i", kind=ArtifactKind.IMAGE, path=str(v2)),
    ]
    records = dedupe_artifacts(arts)
    exact = [r for r in records if r.observations > 1]
    assert exact
    assert exact[0].observations == 2
    assert "2" in exact[0].duplicate_ids
    variants = [r for r in records if "4" == r.artifact.id or "5" == r.artifact.id]
    assert any(r.variant_ids for r in variants)


def test_extract_har_html_adlib_emits_tiers(tmp_path: Path) -> None:
    har_path = write_har(tmp_path / "n.json")
    html_path = write_saved_page(tmp_path / "page")
    adlib_path = write_adlib(tmp_path / "ad.info.json")

    har_art = Artifact(id="h1", incident_id="inc", kind=ArtifactKind.HAR, path=str(har_path), funnel_step=1)
    html_art = Artifact(id="p1", incident_id="inc", kind=ArtifactKind.HTML, path=str(html_path), funnel_step=2)
    ad_art = Artifact(id="a1", incident_id="inc", kind=ArtifactKind.ADLIB_JSON, path=str(adlib_path), funnel_step=1)

    har = parse_har(har_path)
    html = parse_html(html_path)
    adlib = parse_adlib(adlib_path)

    result = extract_all(
        ExtractInput(
            incident_id="inc",
            artifacts=[har_art, html_art, ad_art],
            har={"h1": har},
            html={"p1": html},
            adlib={"a1": adlib},
        )
    )
    types = {e.type for e in result.evidence}
    assert "meta_pixel" in types
    assert "landing_domain" in types or "click_domain" in types
    assert "dom_skeleton" in types
    assert "meta_ad_id" in types
    assert "advertiser_page_id" in types
    assert any(e.tier in {EvidenceTier.A, "A"} for e in result.evidence)
    assert any(e.family in {EvidenceFamily.KIT, "kit", EvidenceFamily.DOMAIN, "domain"} for e in result.evidence)

    ignored = [e for e in result.evidence if e.ignored]
    # jsdelivr library host or CDN IP should produce at least one ignore annotation
    assert any(e.ignore_reason for e in ignored) or any(
        e.ignore_reason for e in result.evidence if e.type == "server_ip"
    )

    assert "har" in result.coverage.kinds_present
    assert "html" in result.coverage.kinds_present
    assert result.coverage.artifact_counts["har"] == 1


def test_extract_marks_cdn_ip_ignored(tmp_path: Path) -> None:
    from backend.pipeline.intake.har import HarParseResult, HarRequest
    from backend.pipeline.models import ParseStatus

    art = Artifact(id="h", incident_id="i", kind=ArtifactKind.HAR, path="x")
    har = HarParseResult(
        parse_status=ParseStatus.OK,
        requests=[
            HarRequest(
                seq=0,
                method="GET",
                url_redacted="https://cdn.example-scam.test/",
                host="cdn.example-scam.test",
                path_pattern="/",
                server_ip="104.16.10.10",
            )
        ],
    )
    result = extract_all(ExtractInput(incident_id="i", artifacts=[art], har={"h": har}))
    ips = [e for e in result.evidence if e.type == "server_ip"]
    assert ips
    assert ips[0].ignored is True
    assert ips[0].ignore_reason == "cdn_ip"
