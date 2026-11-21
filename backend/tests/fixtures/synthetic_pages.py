"""Synthetic HTML / MHTML / bundle builders (tmp only — no dataset files committed)."""

from __future__ import annotations

import json
from email.message import EmailMessage
from email.policy import SMTP
from pathlib import Path

from backend.tests.fixtures.synthetic_har import build_rich_har, write_har

# ≥5 KB so DOM skeleton is emitted.
_BIG_BODY = ("<p>Synthetic paragraph for skeleton size. </p>\n" * 200)


def write_saved_page(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    html_path = root / "offer.html"
    files_dir = root / "offer_files"
    files_dir.mkdir(exist_ok=True)
    (files_dir / "app.js").write_text("console.log('synthetic-app');", encoding="utf-8")
    (files_dir / "hero.png").write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    html_path.write_text(
        "<!doctype html><html><head><title>Synthetic Offer</title>"
        "<script src='https://cdn.jsdelivr.net/npm/jquery@3.7.1/dist/jquery.min.js'></script>"
        "<script src='offer_files/app.js'></script>"
        "</head><body>"
        "<h1>Offer</h1>"
        "<a href='https://land.example-scam.test/next?fbclid=SYNTHFB99'>Continue</a>"
        "<img src='offer_files/hero.png' alt='hero'/>"
        "<form action='https://land.example-scam.test/order?token=SYNTHTOK99' method='post'>"
        "<input name='phone'/><input name='email'/>"
        "</form>"
        f"{_BIG_BODY}"
        "</body></html>",
        encoding="utf-8",
    )
    return html_path


def write_small_page(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / "tiny.html"
    path.write_text(
        "<html><head><title>Tiny</title></head><body><p>hi</p></body></html>",
        encoding="utf-8",
    )
    return path


def write_mhtml(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    msg = EmailMessage(policy=SMTP)
    msg["From"] = "<saved@localhost>"
    msg["Subject"] = "Synthetic MHTML"
    msg["MIME-Version"] = "1.0"
    msg.set_type("multipart/related")

    html = (
        "<html><head><title>MHTML Page</title></head><body>"
        "<a href='https://land.example-scam.test/x?gclid=SYNTHGCL01'>x</a>"
        f"{_BIG_BODY}</body></html>"
    )
    html_part = EmailMessage(policy=SMTP)
    html_part.set_content(html, subtype="html", charset="utf-8")
    html_part.replace_header("Content-Type", 'text/html; charset="utf-8"')
    html_part["Content-Location"] = "https://land.example-scam.test/mhtml"
    msg.attach(html_part)

    img = EmailMessage(policy=SMTP)
    img.set_content(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x00IEND\xaeB`\x82",
        maintype="image",
        subtype="png",
    )
    img["Content-Location"] = "cid:hero"
    msg.attach(img)

    path.write_bytes(msg.as_bytes(policy=SMTP))
    return path


def write_bundle(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "url": "https://land.example-scam.test/landing?fbclid=SYNTHFB77&keep=1",
                "captured_at": "2026-01-02T03:04:05Z",
            }
        ),
        encoding="utf-8",
    )
    (root / "dom.html").write_text(
        "<html><head><title>Bundle DOM</title></head><body>"
        "<a href='https://land.example-scam.test/y?clickid=SYNTHCLK77'>y</a>"
        f"{_BIG_BODY}</body></html>",
        encoding="utf-8",
    )
    write_har(root / "page.json", build_rich_har())
    # Bundle discovery expects page.har; write content with that name in tmp
    # (allowed only under fixtures / tmp — not committed).
    (root / "page.har").write_text(
        (root / "page.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (root / "page.json").unlink()
    resources = root / "resources"
    resources.mkdir(exist_ok=True)
    (resources / "a.css").write_text("body{}", encoding="utf-8")
    (resources / "nested" / "b.js").parent.mkdir(parents=True, exist_ok=True)
    (resources / "nested" / "b.js").write_text("void 0;", encoding="utf-8")
    return root
