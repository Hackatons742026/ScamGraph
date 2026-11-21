"""Evidence extraction registry — plug-in family extractors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from backend.pipeline.extract.extractors import (
    extract_adlib,
    extract_har,
    extract_html,
    extract_media,
)
from backend.pipeline.intake.adlib import AdlibParseResult
from backend.pipeline.intake.har import HarParseResult
from backend.pipeline.intake.html import HtmlParseResult
from backend.pipeline.models import Artifact, Coverage, Evidence, MediaRef
from backend.pipeline.redact import require_salt

ExtractorFn = Callable[..., list[Evidence]]

REGISTRY: dict[str, ExtractorFn] = {
    "har": extract_har,
    "html": extract_html,
    "adlib": extract_adlib,
    "media": extract_media,
}


@dataclass
class ExtractInput:
    """Parsed materials for one incident (parsers may be partially filled)."""

    incident_id: str
    artifacts: list[Artifact] = field(default_factory=list)
    har: dict[str, HarParseResult] = field(default_factory=dict)
    html: dict[str, HtmlParseResult] = field(default_factory=dict)
    adlib: dict[str, AdlibParseResult] = field(default_factory=dict)
    media: list[tuple[Artifact, MediaRef]] = field(default_factory=list)


@dataclass
class ExtractResult:
    evidence: list[Evidence]
    coverage: Coverage


def register_extractor(name: str, fn: ExtractorFn) -> None:
    """Allow later OCR/video families to plug in without API breaks."""
    REGISTRY[name] = fn


def extract_all(data: ExtractInput, *, salt: str | None = None) -> ExtractResult:
    """Run all registered extractors that have input; compute coverage."""
    if salt is None:
        salt = require_salt()

    evidence: list[Evidence] = []
    by_id = {a.id: a for a in data.artifacts}

    for art_id, har in data.har.items():
        art = by_id.get(art_id)
        if art is None:
            continue
        evidence.extend(REGISTRY["har"](art, har, salt=salt))

    for art_id, html in data.html.items():
        art = by_id.get(art_id)
        if art is None:
            continue
        evidence.extend(REGISTRY["html"](art, html, salt=salt))

    for art_id, adlib in data.adlib.items():
        art = by_id.get(art_id)
        if art is None:
            continue
        evidence.extend(REGISTRY["adlib"](art, adlib, salt=salt))

    for art, media in data.media:
        evidence.extend(REGISTRY["media"](art, media, salt=salt))

    evidence = _dedupe_evidence(evidence)
    coverage = coverage_for(data.artifacts, evidence)
    return ExtractResult(evidence=evidence, coverage=coverage)


def coverage_for(artifacts: list[Artifact], evidence: list[Evidence]) -> Coverage:
    kind_counts: dict[str, int] = {}
    for art in artifacts:
        key = art.kind.value if hasattr(art.kind, "value") else str(art.kind)
        kind_counts[key] = kind_counts.get(key, 0) + 1

    present = sorted(kind_counts)
    expected = ["har", "html", "mhtml", "bundle", "image", "video", "adlib_json"]
    missing = [k for k in expected if k not in kind_counts]

    ev_types = sorted({e.type for e in evidence if not e.ignored})
    notes: list[str] = []
    if "har" not in kind_counts:
        notes.append("no HAR")
    if kind_counts.keys() <= {"image", "video", "adlib_json"}:
        notes.append("video only" if "video" in kind_counts else "media only")
    if ev_types:
        notes.append(f"evidence_types={len(ev_types)}")

    return Coverage(
        kinds_present=present,
        kinds_missing=missing,
        artifact_counts=kind_counts,
        notes=notes,
    )


def _dedupe_evidence(rows: list[Evidence]) -> list[Evidence]:
    seen: set[tuple[str, str, str | None]] = set()
    out: list[Evidence] = []
    for row in rows:
        key = (row.type, row.value_hash, row.artifact_id)
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out
