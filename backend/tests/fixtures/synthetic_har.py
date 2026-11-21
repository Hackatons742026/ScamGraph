"""Builders for synthetic HAR JSON (written to tmp at test time — never committed as .har)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _entry(
    *,
    method: str,
    url: str,
    status: int,
    headers_req: list[dict[str, str]] | None = None,
    headers_resp: list[dict[str, str]] | None = None,
    content_text: str | None = None,
    mime: str = "text/html",
    server_ip: str | None = None,
    post_text: str | None = None,
) -> dict[str, Any]:
    request: dict[str, Any] = {
        "method": method,
        "url": url,
        "headers": headers_req or [],
    }
    if post_text is not None:
        request["postData"] = {"mimeType": "application/json", "text": post_text}

    response: dict[str, Any] = {
        "status": status,
        "headers": headers_resp or [],
        "content": {"mimeType": mime, "text": content_text or ""},
    }
    entry: dict[str, Any] = {"request": request, "response": response}
    if server_ip:
        entry["serverIPAddress"] = server_ip
    return entry


def build_rich_har() -> dict[str, Any]:
    """HAR covering redirects, tracking IDs, POST, and secret params/headers."""
    return {
        "log": {
            "version": "1.2",
            "creator": {"name": "synthetic", "version": "1"},
            "entries": [
                _entry(
                    method="GET",
                    url="https://ads.example-scam.test/click?clickid=SYNTHCLICK01&x=1",
                    status=302,
                    headers_resp=[
                        {"name": "Location", "value": "https://land.example-scam.test/pre?fbclid=SYNTHFB01"},
                        {"name": "Set-Cookie", "value": "sid=SYNTHCOOKIE01; Path=/"},
                    ],
                    server_ip="203.0.113.10",
                ),
                _entry(
                    method="GET",
                    url="https://land.example-scam.test/pre?fbclid=SYNTHFB01",
                    status=200,
                    headers_req=[
                        {"name": "Cookie", "value": "sid=SYNTHCOOKIE01"},
                        {"name": "Authorization", "value": "Bearer SYNTHBEARER01"},
                    ],
                    content_text=(
                        "<html><head>"
                        '<meta http-equiv="refresh" content="0;url=https://land.example-scam.test/offer">'
                        "</head><body>"
                        "<script>fbq('init', '123456789012345');</script>"
                        "<script>window.location = 'https://land.example-scam.test/offer?pxl=SYNTHPXL01';</script>"
                        "</body></html>"
                    ),
                    server_ip="203.0.113.11",
                ),
                _entry(
                    method="GET",
                    url="https://www.facebook.com/tr?id=123456789012345&ev=PageView",
                    status=200,
                    mime="image/gif",
                    content_text="<!-- AW-999888777 GTM-ABC123 G-XYZ12345 -->",
                    server_ip="203.0.113.50",
                ),
                _entry(
                    method="POST",
                    url="https://land.example-scam.test/api/v1/order/abc123?token=SYNTHTOKEN01",
                    status=200,
                    post_text='{"lpkey":"SYNTHLPKEY01","note":"ok"}',
                    headers_req=[{"name": "Content-Type", "value": "application/json"}],
                    content_text="<html>thanks</html>",
                    server_ip="203.0.113.11",
                ),
            ],
        }
    }


def build_broken_har_text() -> str:
    return "{not-json"


def write_har(path: Path, doc: dict[str, Any] | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc or build_rich_har()), encoding="utf-8")
    return path
