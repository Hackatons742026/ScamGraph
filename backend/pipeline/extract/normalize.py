"""Normalisation helpers for evidence values before hashing/display."""

from __future__ import annotations

import re
from urllib.parse import urlsplit


def norm_host(host: str) -> str:
    host = (host or "").strip().lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    return host


def norm_domain_from_url(url: str) -> str | None:
    try:
        host = urlsplit(url).hostname
    except Exception:  # noqa: BLE001
        return None
    if not host:
        return None
    return norm_host(host)


def norm_phone_digits(value: str) -> str:
    return re.sub(r"\D+", "", value or "")


def norm_text_sentence(value: str) -> str:
    text = re.sub(r"\s+", " ", (value or "").strip().lower())
    return text


def param_name_set(url: str) -> frozenset[str]:
    try:
        query = urlsplit(url).query
    except Exception:  # noqa: BLE001
        return frozenset()
    names = set()
    for part in query.split("&"):
        if not part:
            continue
        names.add(part.split("=", 1)[0].lower())
    return frozenset(names)
