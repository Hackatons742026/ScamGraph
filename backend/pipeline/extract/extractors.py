"""Family extractors for HAR / HTML / Ad Library / media parse results."""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from backend.pipeline.extract.builders import make_evidence
from backend.pipeline.extract.normalize import (
    is_plausible_domain,
    norm_domain_from_url,
    norm_host,
    norm_phone_digits,
    norm_text_sentence,
    param_name_set,
)
from backend.pipeline.intake.adlib import AdlibParseResult
from backend.pipeline.intake.har import HarParseResult
from backend.pipeline.intake.html import HtmlParseResult
from backend.pipeline.models import (
    Artifact,
    Evidence,
    EvidenceFamily,
    EvidenceTier,
    MediaRef,
)

_PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?\d[\d\s\-()]{7,}\d)"
)
_IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b")
# ``@handle`` only when not part of an e-mail address or a domain; Telegram
# usernames are 5-32 characters.
_TG_RE = re.compile(
    r"(?:t\.me/|telegram\.me/|(?<![\w.@])@)([A-Za-z0-9_]{5,32})(?![\w.]*\.[A-Za-z]{2,})\b",
    re.I,
)
_URL_RE = re.compile(r"\b(?:https?://|www\.)[^\s\"'<>()]+", re.I)
_WA_RE = re.compile(r"(?:wa\.me/|whatsapp\.com/send\?phone=)(\+?\d{6,})", re.I)
_SENTENCE_RE = re.compile(r"[^.!?…]{20,}[.!?…]")


def extract_har(artifact: Artifact, har: HarParseResult, *, salt: str) -> list[Evidence]:
    out: list[Evidence] = []
    step = artifact.funnel_step
    aid = artifact.id

    for hit in har.tracking_ids:
        tier = EvidenceTier.A
        family = None
        etype = hit.kind
        if hit.kind in {"pxl", "fbpx", "pixel_fb", "meta_pixel"}:
            etype = "meta_pixel"
        out.append(
            make_evidence(
                type=etype,
                tier=tier,
                family=family,
                raw_value=hit.value_hash,
                display=hit.display,
                artifact_id=aid,
                funnel_step=step,
                salt=salt,
                value_hash=hit.value_hash,
            )
        )

    param_names: set[str] = set()
    for req in har.requests:
        param_names |= set(param_name_set(req.url_redacted))
        if req.host and is_plausible_domain(req.host):
            host = norm_host(req.host)
            is_click = "/click" in req.path_pattern.lower() or "clickid" in req.url_redacted.lower()
            if is_click:
                out.append(
                    make_evidence(
                        type="click_domain",
                        tier=EvidenceTier.B,
                        family=EvidenceFamily.TDS,
                        raw_value=host,
                        display=host,
                        artifact_id=aid,
                        funnel_step=step,
                        host=host,
                        salt=salt,
                    )
                )
            else:
                out.append(
                    make_evidence(
                        type="landing_domain",
                        tier=EvidenceTier.B,
                        family=EvidenceFamily.DOMAIN,
                        raw_value=host,
                        display=host,
                        artifact_id=aid,
                        funnel_step=step,
                        host=host,
                        salt=salt,
                    )
                )
        if req.server_ip:
            out.append(
                make_evidence(
                    type="server_ip",
                    tier=EvidenceTier.B,
                    family=EvidenceFamily.HOSTING,
                    raw_value=req.server_ip,
                    display=req.server_ip,
                    artifact_id=aid,
                    funnel_step=step,
                    ip=req.server_ip,
                    salt=salt,
                )
            )
        if req.is_post and req.path_pattern:
            out.append(
                make_evidence(
                    type="order_endpoint",
                    tier=EvidenceTier.B,
                    family=EvidenceFamily.KIT,
                    raw_value=f"{norm_host(req.host)}{req.path_pattern}",
                    display=req.path_pattern,
                    artifact_id=aid,
                    funnel_step=step,
                    salt=salt,
                )
            )
            if "/api/" in req.path_pattern:
                out.append(
                    make_evidence(
                        type="kit_api_path",
                        tier=EvidenceTier.B,
                        family=EvidenceFamily.KIT,
                        raw_value=req.path_pattern,
                        display=req.path_pattern,
                        artifact_id=aid,
                        funnel_step=step,
                        salt=salt,
                    )
                )

    if param_names:
        joined = ",".join(sorted(param_names))
        out.append(
            make_evidence(
                type="url_param_set",
                tier=EvidenceTier.B,
                family=EvidenceFamily.KIT,
                raw_value=joined,
                display=joined[:80],
                artifact_id=aid,
                funnel_step=step,
                salt=salt,
            )
        )
    return out


def extract_html(artifact: Artifact, html: HtmlParseResult, *, salt: str) -> list[Evidence]:
    out: list[Evidence] = []
    step = artifact.funnel_step
    aid = artifact.id
    text = html.visible_text or ""

    if html.dom_skeleton_sha256:
        out.append(
            make_evidence(
                type="dom_skeleton",
                tier=EvidenceTier.B,
                family=EvidenceFamily.KIT,
                raw_value=html.dom_skeleton_sha256,
                display=f"skeleton:{html.dom_skeleton_sha256[:12]}",
                artifact_id=aid,
                funnel_step=step,
                doc_bytes=html.main_bytes,
                salt=salt,
                value_hash=html.dom_skeleton_sha256[:32],
            )
        )

    for asset in html.assets:
        # Local sidecar files are compared by content; their location is never kept.
        raw_value = (f"sha256:{asset.content_sha256}" if asset.content_sha256
                     else asset.path_or_url_redacted)
        display = _asset_display(asset.path_or_url_redacted)
        if asset.kind == "script":
            out.append(
                make_evidence(
                    type="js_hash",
                    tier=EvidenceTier.B,
                    family=EvidenceFamily.KIT,
                    raw_value=raw_value,
                    display=display,
                    artifact_id=aid,
                    funnel_step=step,
                    host=None if asset.local else asset.path_or_url_redacted,
                    salt=salt,
                )
            )
        if asset.kind == "image" and asset.local:
            out.append(
                make_evidence(
                    type="content_image",
                    tier=EvidenceTier.B,
                    family=EvidenceFamily.CREATIVE,
                    raw_value=raw_value,
                    display=display,
                    artifact_id=aid,
                    funnel_step=step,
                    salt=salt,
                )
            )

    for link in html.links:
        domain = norm_domain_from_url(link)
        if domain:
            out.append(
                make_evidence(
                    type="landing_domain",
                    tier=EvidenceTier.B,
                    family=EvidenceFamily.DOMAIN,
                    raw_value=domain,
                    display=domain,
                    artifact_id=aid,
                    funnel_step=step,
                    host=domain,
                    salt=salt,
                )
            )

    for form in html.forms:
        if form.action_redacted:
            path = urlsplit(form.action_redacted).path or form.action_redacted
            out.append(
                make_evidence(
                    type="order_endpoint",
                    tier=EvidenceTier.B,
                    family=EvidenceFamily.KIT,
                    raw_value=path,
                    display=path,
                    artifact_id=aid,
                    funnel_step=step,
                    salt=salt,
                )
            )

    out.extend(_text_evidence(text, artifact_id=aid, funnel_step=step, salt=salt))
    return out


def _text_evidence(text: str, *, artifact_id: str, funnel_step: int | None,
                   salt: str) -> list[Evidence]:
    """Contact identifiers and long sentences from visible or pasted text."""
    out: list[Evidence] = []
    aid, step = artifact_id, funnel_step
    for match in _PHONE_RE.finditer(text):
        raw = match.group(0)
        digits = norm_phone_digits(raw)
        out.append(
            make_evidence(
                type="phone",
                tier=EvidenceTier.A,
                family=None,
                raw_value=digits,
                display=_mask_digits(digits),
                artifact_id=aid,
                funnel_step=step,
                salt=salt,
            )
        )
    for match in _IBAN_RE.finditer(text.upper()):
        raw = match.group(0)
        out.append(
            make_evidence(
                type="iban",
                tier=EvidenceTier.A,
                family=None,
                raw_value=raw,
                display=f"{raw[:4]} **** {raw[-4:]}",
                artifact_id=aid,
                funnel_step=step,
                salt=salt,
            )
        )
    for match in _TG_RE.finditer(text):
        handle = match.group(1)
        out.append(
            make_evidence(
                type="telegram",
                tier=EvidenceTier.A,
                family=None,
                raw_value=handle.lower(),
                display=_mask_handle(handle),
                artifact_id=aid,
                funnel_step=step,
                salt=salt,
            )
        )
    for match in _WA_RE.finditer(text):
        num = norm_phone_digits(match.group(1))
        out.append(
            make_evidence(
                type="whatsapp",
                tier=EvidenceTier.A,
                family=None,
                raw_value=num,
                display=_mask_digits(num),
                artifact_id=aid,
                funnel_step=step,
                salt=salt,
            )
        )

    for sentence in _SENTENCE_RE.findall(text):
        words = sentence.split()
        if len(words) < 10:
            continue
        normed = norm_text_sentence(sentence)
        out.append(
            make_evidence(
                type="shared_sentence",
                tier=EvidenceTier.C,
                family=None,
                raw_value=normed,
                display=" ".join(words[:12]) + ("…" if len(words) > 12 else ""),
                artifact_id=aid,
                funnel_step=step,
                salt=salt,
            )
        )
    return out


def extract_text(artifact: Artifact, text: str, *, salt: str) -> list[Evidence]:
    """Evidence from pasted ad text: contacts, sentences and linked domains."""
    out = _text_evidence(text, artifact_id=artifact.id, funnel_step=artifact.funnel_step, salt=salt)
    for match in _URL_RE.finditer(text):
        raw = match.group(0).rstrip(".,;:!?")
        url = raw if "://" in raw else f"https://{raw}"
        out.extend(_url_evidence(artifact, url, salt=salt, with_params=False))
    return out


def extract_url(artifact: Artifact, url: str, *, salt: str) -> list[Evidence]:
    """Evidence from a submitted landing URL: domain and parameter-name set."""
    url = url.strip()
    if url and "://" not in url:
        url = f"https://{url}"
    return _url_evidence(artifact, url, salt=salt, with_params=True)


def _url_evidence(artifact: Artifact, url: str, *, salt: str, with_params: bool) -> list[Evidence]:
    out: list[Evidence] = []
    domain = norm_domain_from_url(url)
    if not domain:
        return out
    lowered = url.lower()
    is_click = "/click" in lowered or "clickid" in lowered
    out.append(
        make_evidence(
            type="click_domain" if is_click else "landing_domain",
            tier=EvidenceTier.B,
            family=EvidenceFamily.TDS if is_click else EvidenceFamily.DOMAIN,
            raw_value=domain,
            display=domain,
            artifact_id=artifact.id,
            funnel_step=artifact.funnel_step,
            host=domain,
            salt=salt,
        )
    )
    names = param_name_set(url)
    if with_params and names:
        joined = ",".join(sorted(names))
        out.append(
            make_evidence(
                type="url_param_set",
                tier=EvidenceTier.B,
                family=EvidenceFamily.KIT,
                raw_value=joined,
                display=joined[:80],
                artifact_id=artifact.id,
                funnel_step=artifact.funnel_step,
                salt=salt,
            )
        )
    return out


def extract_adlib(artifact: Artifact, adlib: AdlibParseResult, *, salt: str) -> list[Evidence]:
    out: list[Evidence] = []
    if adlib.ad_id_hash:
        out.append(
            make_evidence(
                type="meta_ad_id",
                tier=EvidenceTier.A,
                family=None,
                raw_value=adlib.ad_id_hash,
                display=adlib.ad_id or "ad_id",
                artifact_id=artifact.id,
                funnel_step=artifact.funnel_step,
                salt=salt,
                value_hash=adlib.ad_id_hash,
            )
        )
    if adlib.page_id_hash:
        out.append(
            make_evidence(
                type="advertiser_page_id",
                tier=EvidenceTier.A,
                family=None,
                raw_value=adlib.page_id_hash,
                display=adlib.page_id or "page_id",
                artifact_id=artifact.id,
                funnel_step=artifact.funnel_step,
                salt=salt,
                value_hash=adlib.page_id_hash,
            )
        )
    return out


def extract_media(artifact: Artifact, media: MediaRef, *, salt: str) -> list[Evidence]:
    out: list[Evidence] = []
    if media.phash:
        out.append(
            make_evidence(
                type="content_image",
                tier=EvidenceTier.B,
                family=EvidenceFamily.CREATIVE,
                raw_value=media.phash,
                display=f"phash:{media.phash}",
                artifact_id=artifact.id,
                funnel_step=artifact.funnel_step,
                salt=salt,
                value_hash=media.phash,
            )
        )
    if media.ocr_text:
        for sentence in _SENTENCE_RE.findall(media.ocr_text):
            words = sentence.split()
            if len(words) < 10:
                continue
            normed = norm_text_sentence(sentence)
            out.append(
                make_evidence(
                    type="shared_sentence",
                    tier=EvidenceTier.C,
                    family=None,
                    raw_value=normed,
                    display=" ".join(words[:12]) + "…",
                    artifact_id=artifact.id,
                    funnel_step=artifact.funnel_step,
                    salt=salt,
                )
            )
    return out


def _mask_handle(handle: str) -> str:
    """Mask an account handle like phone numbers: ``@ab…yz``."""
    if len(handle) <= 4:
        return "@****"
    return f"@{handle[:2]}…{handle[-2:]}"


def _asset_display(reference: str) -> str:
    """Short, path-free label for a page asset (file name or remote URL tail)."""
    if reference.startswith("local:"):
        return reference[:60]
    return reference[-60:]


def _mask_digits(digits: str) -> str:
    if len(digits) <= 4:
        return "****"
    return f"{digits[:2]}…{digits[-2:]}"
