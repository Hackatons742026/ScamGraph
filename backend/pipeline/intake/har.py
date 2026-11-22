"""HAR intake — streamed entry processing with redaction before retention.

Broken HARs yield ``ParseStatus.FAILED`` and never crash the caller.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import parse_qs, urlsplit

from backend.pipeline.models import ParseStatus
from backend.pipeline.redact import (
    hash_secret,
    redact_headers,
    redact_url,
    require_salt,
)

# Tracking-related query keys (values kept as display-safe hashes when extracted).
_TRACKING_PARAM_KEYS = frozenset({"pxl", "fbpx", "pixel_fb", "id"})
_FBQ_INIT_RE = re.compile(
    r"""fbq\s*\(\s*['"]init['"]\s*,\s*['"](\d{5,20})['"]""",
    re.IGNORECASE,
)
_META_REFRESH_RE = re.compile(
    r"""content\s*=\s*['"]?\s*\d+\s*;\s*url\s*=\s*([^"'>\s]+)""",
    re.IGNORECASE,
)
_JS_LOCATION_RE = re.compile(
    r"""(?:window\.)?location(?:\.href|\.replace)?\s*=\s*['"]([^'"]+)['"]"""
    r"""|location\.replace\(\s*['"]([^'"]+)['"]\s*\)""",
    re.IGNORECASE,
)
_AW_RE = re.compile(r"\b(AW-\d+)\b")
_G_RE = re.compile(r"\b(G-[A-Z0-9]+)\b")
_GTM_RE = re.compile(r"\b(GTM-[A-Z0-9]+)\b")


@dataclass
class HarRequest:
    seq: int
    method: str
    url_redacted: str
    host: str
    path_pattern: str
    status: int | None = None
    server_ip: str | None = None
    mime: str | None = None
    body_sha1: str | None = None
    is_post: bool = False


@dataclass
class RedirectHop:
    seq: int
    url_display: str
    status: int | None
    kind: str  # "3xx" | "meta" | "js"


@dataclass
class TrackingHit:
    kind: str
    value_hash: str
    display: str
    source: str  # "url" | "body"


@dataclass
class HarParseResult:
    parse_status: ParseStatus
    error: str | None = None
    requests: list[HarRequest] = field(default_factory=list)
    redirect_chain: list[RedirectHop] = field(default_factory=list)
    tracking_ids: list[TrackingHit] = field(default_factory=list)
    hosts: list[str] = field(default_factory=list)
    server_ips: list[str] = field(default_factory=list)
    post_endpoints: list[str] = field(default_factory=list)
    captured_at: str | None = None  # earliest entry startedDateTime (RFC 3339)


def parse_har(path: Path | str, *, salt: str | None = None) -> HarParseResult:
    """Parse a HAR file. Never raises for malformed input — returns FAILED."""
    try:
        if salt is None:
            salt = require_salt()
        return _parse_har(Path(path), salt=salt)
    except Exception as exc:  # noqa: BLE001 — isolation boundary
        return HarParseResult(
            parse_status=ParseStatus.FAILED,
            error=_short_error(exc),
        )


def iter_har_entries(path: Path, *, salt: str | None = None) -> Iterator[dict[str, Any]]:
    """Yield HAR ``log.entries`` items one at a time (streamed processing).

    Loads the document via a streaming JSON decoder when possible; falls back
    to a full load. Raises on structural failure — :func:`parse_har` catches.
    """
    if salt is None:
        require_salt()
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        # Prefer ijson if installed (large HARs); otherwise stdlib load.
        try:
            import ijson  # type: ignore[import-not-found]

            for entry in ijson.items(fh, "log.entries.item"):
                if isinstance(entry, dict):
                    yield entry
            return
        except ImportError:
            fh.seek(0)
            data = json.load(fh)
        except Exception:
            fh.seek(0)
            data = json.load(fh)

    if not isinstance(data, dict):
        raise ValueError("HAR root must be an object")
    log = data.get("log")
    if not isinstance(log, dict):
        raise ValueError("HAR missing log object")
    entries = log.get("entries")
    if entries is None:
        return
    if not isinstance(entries, list):
        raise ValueError("HAR log.entries must be a list")
    for entry in entries:
        if isinstance(entry, dict):
            yield entry


def _parse_har(path: Path, *, salt: str) -> HarParseResult:
    if not path.is_file():
        return HarParseResult(
            parse_status=ParseStatus.FAILED,
            error="file not found",
        )

    requests: list[HarRequest] = []
    redirects: list[RedirectHop] = []
    tracking: list[TrackingHit] = []
    hosts: set[str] = set()
    ips: set[str] = set()
    posts: list[str] = []
    hop_seq = 0
    partial = False
    started_times: list[datetime] = []

    try:
        entry_iter = iter_har_entries(path, salt=salt)
    except Exception as exc:  # noqa: BLE001
        return HarParseResult(
            parse_status=ParseStatus.FAILED,
            error=_short_error(exc),
        )

    try:
        for seq, entry in enumerate(entry_iter):
            try:
                req_obj = entry.get("request") or {}
                resp_obj = entry.get("response") or {}
                if not isinstance(req_obj, dict):
                    req_obj = {}
                if not isinstance(resp_obj, dict):
                    resp_obj = {}

                started = _parse_time(entry.get("startedDateTime"))
                if started is not None:
                    started_times.append(started)
                method = str(req_obj.get("method") or "GET").upper()
                raw_url = str(req_obj.get("url") or "")
                url_redacted = redact_url(raw_url, salt=salt)
                parts = urlsplit(url_redacted)
                host = parts.hostname or ""
                if host:
                    hosts.add(host.lower())

                path_pattern = _path_pattern(parts.path)

                status = resp_obj.get("status")
                status_i = int(status) if isinstance(status, int) else None
                if status_i is None and isinstance(status, str) and status.isdigit():
                    status_i = int(status)

                server_ip = entry.get("serverIPAddress")
                if isinstance(server_ip, str) and server_ip:
                    ips.add(server_ip)

                mime = None
                content = resp_obj.get("content")
                if isinstance(content, dict):
                    mime = content.get("mimeType")
                    if isinstance(mime, str):
                        mime = mime.split(";")[0].strip() or None

                headers_in = _headers_list(req_obj.get("headers"))
                headers_out = _headers_list(resp_obj.get("headers"))
                # Force redaction side-effects / equality stability (values discarded).
                redact_headers(headers_in, salt=salt)
                redact_headers(headers_out, salt=salt)

                post_text = _post_body_text(req_obj)
                body_sha1 = None
                if post_text:
                    body_sha1 = hashlib.sha1(
                        post_text.encode("utf-8", errors="replace")
                    ).hexdigest()

                is_post = method == "POST" or bool(post_text)
                if is_post and path_pattern:
                    endpoint = f"{host}{path_pattern}" if host else path_pattern
                    if endpoint not in posts:
                        posts.append(endpoint)

                requests.append(
                    HarRequest(
                        seq=seq,
                        method=method,
                        url_redacted=url_redacted,
                        host=host,
                        path_pattern=path_pattern,
                        status=status_i,
                        server_ip=server_ip if isinstance(server_ip, str) else None,
                        mime=mime,
                        body_sha1=body_sha1,
                        is_post=is_post,
                    )
                )

                # --- redirects ---
                if status_i is not None and 300 <= status_i < 400:
                    location = _header_value(headers_out, "Location")
                    if location:
                        hop_seq += 1
                        redirects.append(
                            RedirectHop(
                                seq=hop_seq,
                                url_display=redact_url(location, salt=salt),
                                status=status_i,
                                kind="3xx",
                            )
                        )

                resp_text = _response_text(resp_obj)
                if resp_text:
                    for url in _meta_refresh_urls(resp_text):
                        hop_seq += 1
                        redirects.append(
                            RedirectHop(
                                seq=hop_seq,
                                url_display=redact_url(url, salt=salt),
                                status=status_i,
                                kind="meta",
                            )
                        )
                        tracking.extend(_tracking_from_url(url, salt=salt))
                    for url in _js_location_urls(resp_text):
                        hop_seq += 1
                        redirects.append(
                            RedirectHop(
                                seq=hop_seq,
                                url_display=redact_url(url, salt=salt),
                                status=status_i,
                                kind="js",
                            )
                        )
                        tracking.extend(_tracking_from_url(url, salt=salt))

                # --- tracking IDs ---
                tracking.extend(_tracking_from_url(raw_url, salt=salt))
                if resp_text:
                    tracking.extend(_tracking_from_body(resp_text, salt=salt))
                if post_text:
                    tracking.extend(_tracking_from_body(post_text, salt=salt))

            except Exception:  # noqa: BLE001 — one bad entry → partial
                partial = True
                continue
    except Exception as exc:  # noqa: BLE001
        if not requests:
            return HarParseResult(
                parse_status=ParseStatus.FAILED,
                error=_short_error(exc),
            )
        partial = True

    # Dedupe tracking by (kind, value_hash)
    seen: set[tuple[str, str]] = set()
    unique_tracking: list[TrackingHit] = []
    for hit in tracking:
        key = (hit.kind, hit.value_hash)
        if key in seen:
            continue
        seen.add(key)
        unique_tracking.append(hit)

    status = ParseStatus.PARTIAL if partial else ParseStatus.OK
    return HarParseResult(
        parse_status=status,
        error=None,
        requests=requests,
        redirect_chain=redirects,
        tracking_ids=unique_tracking,
        hosts=sorted(hosts),
        server_ips=sorted(ips),
        post_endpoints=posts,
        captured_at=min(started_times).isoformat() if started_times else None,
    )


def _parse_time(value: Any) -> datetime | None:
    """Parse a HAR ``startedDateTime`` into an aware UTC datetime."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _headers_list(raw: Any) -> list[tuple[str, str]]:
    if not isinstance(raw, list):
        return []
    out: list[tuple[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        value = item.get("value")
        if isinstance(name, str) and isinstance(value, str):
            out.append((name, value))
    return out


def _header_value(headers: list[tuple[str, str]], name: str) -> str | None:
    target = name.lower()
    for key, value in headers:
        if key.lower() == target:
            return value
    return None


def _post_body_text(req_obj: dict[str, Any]) -> str:
    post = req_obj.get("postData")
    if not isinstance(post, dict):
        return ""
    text = post.get("text")
    return text if isinstance(text, str) else ""


def _response_text(resp_obj: dict[str, Any]) -> str:
    content = resp_obj.get("content")
    if not isinstance(content, dict):
        return ""
    text = content.get("text")
    if not isinstance(text, str):
        return ""
    # Skip huge binaries; keep enough for meta/JS/tracking sniffing.
    if len(text) > 500_000:
        return text[:500_000]
    encoding = content.get("encoding")
    if encoding == "base64":
        return ""  # do not decode opaque binaries
    return text


def _path_pattern(path: str) -> str:
    if not path:
        return "/"
    # Replace id-like path segments with {id}.
    parts = []
    for seg in path.split("/"):
        if not seg:
            parts.append(seg)
            continue
        if (
            re.fullmatch(r"[0-9a-fA-F]{8,}", seg)
            or re.fullmatch(r"\d{3,}", seg)
            or (
                len(seg) >= 6
                and re.fullmatch(r"[A-Za-z0-9_-]+", seg)
                and any(ch.isdigit() for ch in seg)
            )
        ):
            parts.append("{id}")
        else:
            parts.append(seg)
    return "/".join(parts) or "/"


def _tracking_from_url(url: str, *, salt: str) -> list[TrackingHit]:
    hits: list[TrackingHit] = []
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    qs = parse_qs(parts.query, keep_blank_values=False)

    if "facebook.com" in host and parts.path.rstrip("/").endswith("/tr"):
        for value in qs.get("id", []):
            hits.append(
                TrackingHit(
                    kind="meta_pixel",
                    value_hash=hash_secret(value, salt=salt),
                    display=_mask_id(value),
                    source="url",
                )
            )

    for key in ("pxl", "fbpx", "pixel_fb"):
        for value in qs.get(key, []):
            hits.append(
                TrackingHit(
                    kind=key,
                    value_hash=hash_secret(value, salt=salt),
                    display=_mask_id(value),
                    source="url",
                )
            )

    combined = url
    for regex, kind in ((_AW_RE, "aw_id"), (_G_RE, "g_id"), (_GTM_RE, "gtm_id")):
        for match in regex.finditer(combined):
            value = match.group(1)
            hits.append(
                TrackingHit(
                    kind=kind,
                    value_hash=hash_secret(value, salt=salt),
                    display=value if value.startswith(("AW-", "G-", "GTM-")) else _mask_id(value),
                    source="url",
                )
            )
    return hits


def _tracking_from_body(text: str, *, salt: str) -> list[TrackingHit]:
    hits: list[TrackingHit] = []
    for match in _FBQ_INIT_RE.finditer(text):
        value = match.group(1)
        hits.append(
            TrackingHit(
                kind="meta_pixel",
                value_hash=hash_secret(value, salt=salt),
                display=_mask_id(value),
                source="body",
            )
        )
    for regex, kind in ((_AW_RE, "aw_id"), (_G_RE, "g_id"), (_GTM_RE, "gtm_id")):
        for match in regex.finditer(text):
            value = match.group(1)
            hits.append(
                TrackingHit(
                    kind=kind,
                    value_hash=hash_secret(value, salt=salt),
                    display=value,
                    source="body",
                )
            )
    return hits


def _meta_refresh_urls(text: str) -> list[str]:
    return [m.group(1).strip() for m in _META_REFRESH_RE.finditer(text)]


def _js_location_urls(text: str) -> list[str]:
    urls: list[str] = []
    for match in _JS_LOCATION_RE.finditer(text):
        url = match.group(1) or match.group(2)
        if url:
            urls.append(url)
    return urls


def _mask_id(value: str) -> str:
    if len(value) <= 4:
        return "****"
    return f"{value[:2]}…{value[-2:]}"


def _short_error(exc: BaseException) -> str:
    msg = f"{type(exc).__name__}: {exc}"
    return msg[:200]
