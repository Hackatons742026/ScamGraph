"""Meta Ad Library ``*.info.json`` (yt-dlp facebook:ads) parser."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path

from backend.pipeline.models import ParseStatus
from backend.pipeline.redact import hash_secret, require_salt


@dataclass
class AdlibParseResult:
    parse_status: ParseStatus
    error: str | None = None
    ad_id: str | None = None
    ad_id_hash: str | None = None
    page_id: str | None = None
    page_id_hash: str | None = None
    title: str | None = None
    extractor: str | None = None
    raw_keys: list[str] | None = None
    captured_at: str | None = None


def parse_adlib(path: Path | str, *, salt: str | None = None) -> AdlibParseResult:
    """Extract ad ID + advertiser page ID. Never raises."""
    try:
        if salt is None:
            salt = require_salt()
        return _parse(Path(path), salt=salt)
    except Exception as exc:  # noqa: BLE001
        return AdlibParseResult(
            parse_status=ParseStatus.FAILED,
            error=f"{type(exc).__name__}: {exc}"[:200],
        )


def _parse(path: Path, *, salt: str) -> AdlibParseResult:
    if not path.is_file():
        return AdlibParseResult(parse_status=ParseStatus.FAILED, error="file not found")

    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:  # noqa: BLE001
        return AdlibParseResult(
            parse_status=ParseStatus.FAILED,
            error=f"{type(exc).__name__}: {exc}"[:200],
        )
    if not isinstance(data, dict):
        return AdlibParseResult(
            parse_status=ParseStatus.FAILED,
            error="Ad Library JSON root must be an object",
        )

    extractor = data.get("extractor")
    extractor_s = str(extractor) if extractor is not None else None

    ad_id = _first_str(
        data,
        ("ad_id", "ad_archive_id", "id", "adArchiveID", "adArchiveId"),
    )
    page_id = _first_str(
        data,
        ("page_id", "pageID", "advertiser_id", "advertiser", "page_name"),
    )
    # advertiser may be a nested object
    if page_id is None and isinstance(data.get("advertiser"), dict):
        page_id = _first_str(data["advertiser"], ("id", "page_id", "name"))

    title = _first_str(data, ("title", "full_title", "description"))

    if ad_id is None and page_id is None:
        return AdlibParseResult(
            parse_status=ParseStatus.PARTIAL,
            error="no ad_id/page_id fields",
            extractor=extractor_s,
            raw_keys=sorted(str(k) for k in data.keys()),
            title=title,
        )

    return AdlibParseResult(
        parse_status=ParseStatus.OK,
        ad_id=_mask(ad_id) if ad_id else None,
        ad_id_hash=hash_secret(ad_id, salt=salt) if ad_id else None,
        page_id=_mask(page_id) if page_id else None,
        page_id_hash=hash_secret(page_id, salt=salt) if page_id else None,
        title=title,
        extractor=extractor_s,
        raw_keys=sorted(str(k) for k in data.keys()),
        captured_at=_captured_at(data),
    )


def _captured_at(data: dict) -> str | None:
    """yt-dlp ``timestamp``, ``upload_date`` (YYYYMMDD), or download ``epoch``."""
    stamp = data.get("timestamp")
    if isinstance(stamp, (int, float)) and stamp > 0:
        try:
            return datetime.fromtimestamp(stamp, tz=timezone.utc).isoformat()
        except (OverflowError, OSError, ValueError):
            pass
    day = data.get("upload_date")
    if isinstance(day, str) and len(day) == 8 and day.isdigit():
        try:
            return datetime.strptime(day, "%Y%m%d").replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            pass
    epoch = data.get("epoch")  # when yt-dlp captured the ad
    if isinstance(epoch, (int, float)) and epoch > 0:
        try:
            return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()
        except (OverflowError, OSError, ValueError):
            return None
    return None


def _first_str(data: dict, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, (str, int)) and str(value).strip():
            return str(value).strip()
    return None


def _mask(value: str) -> str:
    if len(value) <= 4:
        return "****"
    return f"{value[:2]}…{value[-2:]}"
