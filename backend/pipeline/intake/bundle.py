"""Page-capture bundle parser (``manifest.json`` + DOM + nested HAR + resources)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.pipeline.intake.har import HarParseResult, parse_har
from backend.pipeline.intake.html import HtmlParseResult, parse_html
from backend.pipeline.models import ParseStatus
from backend.pipeline.redact import redact_url, require_salt


@dataclass
class BundleParseResult:
    parse_status: ParseStatus
    error: str | None = None
    url_redacted: str | None = None
    captured_at: str | None = None
    manifest: dict[str, Any] = field(default_factory=dict)
    html: HtmlParseResult | None = None
    har: HarParseResult | None = None
    resource_count: int = 0
    resource_names: list[str] = field(default_factory=list)


def parse_bundle(path: Path | str, *, salt: str | None = None) -> BundleParseResult:
    """Parse a capture-bundle directory. Never raises for malformed input."""
    try:
        if salt is None:
            salt = require_salt()
        return _parse_bundle(Path(path), salt=salt)
    except Exception as exc:  # noqa: BLE001
        return BundleParseResult(
            parse_status=ParseStatus.FAILED,
            error=_short_error(exc),
        )


def _parse_bundle(root: Path, *, salt: str) -> BundleParseResult:
    if root.is_file() and root.name == "manifest.json":
        root = root.parent
    if not root.is_dir():
        return BundleParseResult(
            parse_status=ParseStatus.FAILED,
            error="bundle root is not a directory",
        )

    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        return BundleParseResult(
            parse_status=ParseStatus.FAILED,
            error="manifest.json missing",
        )

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8", errors="replace"))
        if not isinstance(manifest, dict):
            raise ValueError("manifest root must be an object")
    except Exception as exc:  # noqa: BLE001
        return BundleParseResult(
            parse_status=ParseStatus.FAILED,
            error=_short_error(exc),
        )

    raw_url = manifest.get("url") or manifest.get("final_url") or manifest.get("page_url")
    url_redacted = None
    if isinstance(raw_url, str) and raw_url:
        url_redacted = redact_url(raw_url, salt=salt)

    captured_at = None
    for key in ("captured_at", "timestamp", "startedDateTime", "date"):
        value = manifest.get(key)
        if isinstance(value, str) and value:
            captured_at = value
            break

    # Redact any other string URL-looking fields in a shallow copy for retention.
    safe_manifest = _redact_manifest(manifest, salt=salt)

    html_result = None
    dom_path = _first_existing(root, ("dom.html", "page.html", "index.html"))
    if dom_path is not None:
        html_result = parse_html(dom_path, salt=salt)

    har_result = None
    har_path = _first_existing(root, ("page.har", "network.har", ".har"))
    if har_path is not None:
        har_result = parse_har(har_path, salt=salt)

    resources_dir = root / "resources"
    resource_names: list[str] = []
    if resources_dir.is_dir():
        for p in sorted(resources_dir.rglob("*")):
            if p.is_file():
                resource_names.append(p.relative_to(resources_dir).as_posix())

    statuses = []
    if html_result is not None:
        statuses.append(html_result.parse_status)
    if har_result is not None:
        statuses.append(har_result.parse_status)

    if html_result is None and har_result is None:
        status = ParseStatus.PARTIAL
        error = "manifest ok but no DOM/HAR found"
    elif any(s == ParseStatus.FAILED for s in statuses) and any(
        s == ParseStatus.OK for s in statuses
    ):
        status = ParseStatus.PARTIAL
        error = None
    elif statuses and all(s == ParseStatus.FAILED for s in statuses):
        status = ParseStatus.FAILED
        error = "DOM and HAR parse failed"
    elif any(s == ParseStatus.PARTIAL for s in statuses):
        status = ParseStatus.PARTIAL
        error = None
    else:
        status = ParseStatus.OK
        error = None

    return BundleParseResult(
        parse_status=status,
        error=error,
        url_redacted=url_redacted,
        captured_at=captured_at,
        manifest=safe_manifest,
        html=html_result,
        har=har_result,
        resource_count=len(resource_names),
        resource_names=resource_names,
    )


def _first_existing(root: Path, names: tuple[str, ...]) -> Path | None:
    for name in names:
        candidate = root / name
        if candidate.is_file():
            return candidate
    return None


def _redact_manifest(manifest: dict[str, Any], *, salt: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in manifest.items():
        if isinstance(value, str) and (
            "url" in key.lower()
            or value.startswith("http://")
            or value.startswith("https://")
        ):
            out[key] = redact_url(value, salt=salt)
        else:
            out[key] = value
    return out


def _short_error(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"[:200]
