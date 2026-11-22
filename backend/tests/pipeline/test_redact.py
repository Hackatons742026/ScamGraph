"""Tests for salt-gated redaction helpers."""

from __future__ import annotations

import os

import pytest

from backend.pipeline.redact import (
    MissingSaltError,
    counting_redactions,
    hash_secret,
    redact_headers,
    redact_url,
    require_salt,
)


@pytest.fixture(autouse=True)
def _salt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCAMGRAPH_SALT", "unit-test-salt")


def test_missing_salt_fails_loudly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SCAMGRAPH_SALT", raising=False)
    with pytest.raises(MissingSaltError):
        require_salt()


def test_hash_is_stable_and_truncated() -> None:
    a = hash_secret("SYNTHVALUE01")
    b = hash_secret("SYNTHVALUE01")
    assert a == b
    assert len(a) == 12
    assert a != "SYNTHVALUE01"


def test_redact_url_hashes_secret_params_only() -> None:
    url = "https://land.example-scam.test/x?fbclid=SYNTHFB01&keep=1&token=SYNTHTOKEN01"
    out = redact_url(url)
    assert "SYNTHFB01" not in out
    assert "SYNTHTOKEN01" not in out
    assert "keep=1" in out
    assert "fbclid=" in out
    assert hash_secret("SYNTHFB01") in out


def test_redact_headers_cookie_and_authorization() -> None:
    redacted = redact_headers(
        [
            ("Cookie", "sid=SYNTHCOOKIE01"),
            ("X-Trace", "ok"),
            ("Authorization", "Bearer SYNTHBEARER01"),
        ]
    )
    by_name = {k.lower(): v for k, v in redacted}
    assert by_name["cookie"] == hash_secret("sid=SYNTHCOOKIE01")
    assert by_name["authorization"] == hash_secret("Bearer SYNTHBEARER01")
    assert by_name["x-trace"] == "ok"
    assert os.environ["SCAMGRAPH_SALT"] == "unit-test-salt"


def test_counting_redactions_tracks_url_and_header_secrets() -> None:
    with counting_redactions() as box:
        redact_url("https://land.example-scam.test/x?fbclid=SYNTHFB01&keep=1&token=SYNTHTOKEN01")
        redact_headers(
            [
                ("Cookie", "sid=SYNTHCOOKIE01"),
                ("X-Trace", "ok"),
                ("Authorization", "Bearer SYNTHBEARER01"),
            ]
        )
    # fbclid + token + Cookie + Authorization
    assert box[0] == 4
