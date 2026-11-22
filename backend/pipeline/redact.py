"""Secret redaction — privacy gate before any storage, logging or display.

Missing ``SCAMGRAPH_SALT`` fails loudly (no default). Equality of two redacted
values remains stable for the same salt + raw value.
"""

from __future__ import annotations

import hashlib
import os
import re
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Query / form parameter names whose values must be hashed.
SECRET_PARAM_NAMES = frozenset(
    {
        "access_token",
        "token",
        "key",
        "lpkey",
        "fbclid",
        "gclid",
        "clickid",
        "sessionid",
        "session_id",
        "sid",
        "userid",
        "user_id",
        "uid",
        # Tracking identifiers — stored/displayed only as hashes.
        "pxl",
        "fbpx",
        "pixel_fb",
    }
)

# Header names whose values must be hashed (compared case-insensitively).
SECRET_HEADER_NAMES = frozenset(
    {
        "cookie",
        "set-cookie",
        "authorization",
    }
)

_SALT_ENV = "SCAMGRAPH_SALT"

# When set, each redaction of a secret value increments this counter.
_redact_count: ContextVar[int | None] = ContextVar("scamgraph_redact_count", default=None)


class MissingSaltError(RuntimeError):
    """Raised when ``SCAMGRAPH_SALT`` is unset or empty."""


def require_salt() -> str:
    """Return the configured salt or raise :class:`MissingSaltError`."""
    salt = os.environ.get(_SALT_ENV)
    if salt is None or salt == "":
        raise MissingSaltError(
            f"{_SALT_ENV} is required and must not be empty "
            "(set per machine via env; never commit a default)."
        )
    return salt


def _bump_redact() -> None:
    current = _redact_count.get()
    if current is not None:
        _redact_count.set(current + 1)


@contextmanager
def counting_redactions() -> Iterator[list[int]]:
    """Accumulate how many secret values are hashed while the context is active.

    Yields a one-element list ``[count]`` that is updated on exit (and live).
    """
    token = _redact_count.set(0)
    box = [0]
    try:
        yield box
        box[0] = _redact_count.get() or 0
    finally:
        _redact_count.reset(token)


def secrets_redacted_count() -> int:
    """Current count inside :func:`counting_redactions`, else 0."""
    return _redact_count.get() or 0


def hash_secret(value: str, *, salt: str | None = None) -> str:
    """Return ``sha256(salt + value)`` truncated to 12 hex chars."""
    if salt is None:
        salt = require_salt()
    material = f"{salt}{value}".encode("utf-8", errors="replace")
    return hashlib.sha256(material).hexdigest()[:12]


def redact_value(value: str, *, salt: str | None = None) -> str:
    """Hash a secret value for storage / comparison."""
    out = hash_secret(value, salt=salt)
    _bump_redact()
    return out


def is_secret_param(name: str) -> bool:
    return name.lower() in SECRET_PARAM_NAMES


def is_secret_header(name: str) -> bool:
    return name.lower() in SECRET_HEADER_NAMES


def redact_url(url: str, *, salt: str | None = None) -> str:
    """Return ``url`` with secret query-parameter values hashed.

    Fragment is dropped (never needed for evidence). Non-HTTP schemes and
    unparseable strings are returned unchanged aside from secret-looking
    ``name=value`` pairs rewritten via a conservative regex fallback.
    """
    if not url:
        return url
    if salt is None:
        salt = require_salt()

    parts = urlsplit(url)
    if parts.query:
        pairs = []
        for key, value in parse_qsl(parts.query, keep_blank_values=True):
            if is_secret_param(key):
                pairs.append((key, hash_secret(value, salt=salt)))
                _bump_redact()
            else:
                pairs.append((key, value))
        new_query = urlencode(pairs, doseq=True)
        return urlunsplit(
            (parts.scheme, parts.netloc, parts.path, new_query, "")
        )

    # Fallback for odd strings that are not a proper URL but embed params.
    def _sub(match: re.Match[str]) -> str:
        key, raw = match.group(1), match.group(2)
        if is_secret_param(key):
            _bump_redact()
            return f"{key}={hash_secret(raw, salt=salt)}"
        return match.group(0)

    return re.sub(
        r"([A-Za-z_][A-Za-z0-9_]*)=([^&\s#]*)",
        _sub,
        url,
    )


def redact_headers(
    headers: list[tuple[str, str]] | dict[str, str],
    *,
    salt: str | None = None,
) -> list[tuple[str, str]]:
    """Return headers with secret values hashed; order preserved for lists."""
    if salt is None:
        salt = require_salt()
    if isinstance(headers, dict):
        items = list(headers.items())
    else:
        items = list(headers)
    out: list[tuple[str, str]] = []
    for name, value in items:
        if is_secret_header(name):
            out.append((name, hash_secret(value, salt=salt)))
            _bump_redact()
        else:
            out.append((name, value))
    return out


def redact_header_value(name: str, value: str, *, salt: str | None = None) -> str:
    """Redact a single header value when the name is sensitive."""
    if is_secret_header(name):
        out = hash_secret(value, salt=salt)
        _bump_redact()
        return out
    return value
