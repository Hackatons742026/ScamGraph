"""MHTML parser — split via the stdlib ``email`` package, then reuse HTML intake."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from email import policy
from email.parser import BytesParser
from pathlib import Path

from backend.pipeline.intake.html import HtmlParseResult, parse_html
from backend.pipeline.models import ParseStatus
from backend.pipeline.redact import require_salt


@dataclass
class MhtmlPart:
    content_type: str
    location: str | None
    size: int


@dataclass
class MhtmlParseResult:
    parse_status: ParseStatus
    error: str | None = None
    html: HtmlParseResult | None = None
    parts: list[MhtmlPart] = field(default_factory=list)
    part_count: int = 0


def parse_mhtml(path: Path | str, *, salt: str | None = None) -> MhtmlParseResult:
    """Parse an MHTML/MHT capture. Never raises for malformed input."""
    try:
        if salt is None:
            salt = require_salt()
        return _parse_mhtml(Path(path), salt=salt)
    except Exception as exc:  # noqa: BLE001
        return MhtmlParseResult(
            parse_status=ParseStatus.FAILED,
            error=_short_error(exc),
        )


def _parse_mhtml(path: Path, *, salt: str) -> MhtmlParseResult:
    if not path.is_file():
        return MhtmlParseResult(parse_status=ParseStatus.FAILED, error="file not found")

    raw = path.read_bytes()
    try:
        msg = BytesParser(policy=policy.default).parsebytes(raw)
    except Exception as exc:  # noqa: BLE001
        return MhtmlParseResult(
            parse_status=ParseStatus.FAILED,
            error=_short_error(exc),
        )

    parts: list[MhtmlPart] = []
    html_bytes: bytes | None = None

    payloads = msg.walk() if msg.is_multipart() else [msg]
    for part in payloads:
        ctype = part.get_content_type()
        if ctype == "multipart/related" or ctype.startswith("multipart/"):
            continue
        payload = part.get_payload(decode=True)
        if not isinstance(payload, bytes):
            text = part.get_content()
            payload = text.encode("utf-8", errors="replace") if isinstance(text, str) else b""
        location = part.get("Content-Location") or part.get("Content-ID")
        parts.append(
            MhtmlPart(
                content_type=ctype,
                location=str(location) if location else None,
                size=len(payload),
            )
        )
        if html_bytes is None and ctype in {"text/html", "application/xhtml+xml"}:
            html_bytes = payload

    if html_bytes is None:
        return MhtmlParseResult(
            parse_status=ParseStatus.PARTIAL,
            error="no text/html part found",
            parts=parts,
            part_count=len(parts),
        )

    with tempfile.TemporaryDirectory(prefix="sg-mhtml-") as tmp:
        html_path = Path(tmp) / "main.html"
        html_path.write_bytes(html_bytes)
        html_result = parse_html(html_path, salt=salt)

    status = html_result.parse_status
    if status == ParseStatus.OK and len(parts) == 0:
        status = ParseStatus.PARTIAL

    return MhtmlParseResult(
        parse_status=status,
        error=html_result.error,
        html=html_result,
        parts=parts,
        part_count=len(parts),
    )


def _short_error(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"[:200]
