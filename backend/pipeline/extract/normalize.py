"""Normalisation helpers for evidence values before hashing/display."""

from __future__ import annotations

import re
from urllib.parse import urlsplit


def norm_host(host: str) -> str:
    host = (host or "").strip().lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    return host


_LABEL_RE = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")
_TLD_RE = re.compile(r"^(?:[a-z]{2,63}|xn--[a-z0-9-]{1,59})$")


def is_plausible_domain(host: str) -> bool:
    """True for a registrable-looking DNS name (``offer.example.test``).

    Rejects single-label hosts (``delivered``, ``localhost``), IP literals and
    malformed labels so relative links or file names never become domains.
    """
    host = norm_host(host)
    labels = host.split(".")
    if len(labels) < 2 or not all(_LABEL_RE.match(label) for label in labels):
        return False
    return bool(_TLD_RE.match(labels[-1]))


def norm_domain_from_url(url: str) -> str | None:
    try:
        parts = urlsplit(url)
        host = parts.hostname
    except Exception:  # noqa: BLE001
        return None
    if not host or parts.scheme not in {"http", "https", ""}:
        return None
    host = norm_host(host)
    return host if is_plausible_domain(host) else None


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
