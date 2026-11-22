"""Family extractors for HAR / HTML / Ad Library / media parse results."""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from backend.pipeline.extract.builders import make_evidence
from backend.pipeline.extract.ignore import is_third_party_host
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
# E.164 numbers have at most 15 digits; national numbers at least 9.
_PHONE_DIGITS = range(9, 16)
# IBAN with optional single spaces/hyphens between characters (``PL61 1090 …``).
_IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}(?:[ \-]?[A-Z0-9]){11,30}\b")
# Polish domestic account number (NRB): 26 digits, usually ``61 1090 1014 …``.
_NRB_RE = re.compile(r"(?<![\dA-Z])\d{2}(?:[ \-]?\d{4}){6}(?!\d)")
_EMAIL_RE = re.compile(r"(?<![\w.+-])[A-Za-z0-9._%+-]{1,64}@(?:[A-Za-z0-9-]{1,63}\.)+[A-Za-z]{2,24}\b")
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
        if not is_third_party_host(req.host):
            param_names |= kit_param_names(req.url_redacted)
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

    for script in har.scripts:
        # Scripts are compared by content; the same file name alone proves nothing.
        out.append(
            make_evidence(
                type="js_hash",
                tier=EvidenceTier.B,
                family=EvidenceFamily.KIT,
                raw_value=f"sha256:{script.sha256}",
                display=f"js:{script.name}"[:60],
                artifact_id=aid,
                funnel_step=step,
                host=script.host,
                salt=salt,
            )
        )

    if len(param_names) >= 2:
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
        if asset.local and not asset.content_sha256:
            continue  # the file was not saved with the page: a bare file name proves nothing
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
    visible_emails = {value for value, _ in find_emails(text)}
    for link in html.links:
        if link.lower().startswith("mailto:"):
            for value, _ in find_emails(link[7:]):
                if value not in visible_emails:
                    visible_emails.add(value)
                    out.append(_email_evidence(value, artifact_id=aid, funnel_step=step, salt=salt))
    return out


def _valid_iban(compact: str) -> bool:
    """ISO 13616 mod-97 check, so random letter/digit runs are not accounts."""
    if not 15 <= len(compact) <= 34:
        return False
    rearranged = compact[4:] + compact[:4]
    try:
        return int("".join(str(int(ch, 36)) for ch in rearranged)) % 97 == 1
    except ValueError:
        return False


# Official IBAN lengths for countries seen in Central European fraud reports.
_IBAN_LENGTHS = {
    "PL": 28, "DE": 22, "GB": 22, "FR": 27, "ES": 24, "IT": 27, "NL": 18, "BE": 16, "AT": 20,
    "CH": 21, "CZ": 24, "SK": 24, "HU": 28, "RO": 24, "BG": 22, "HR": 21, "SI": 19, "LT": 20,
    "LV": 21, "EE": 20, "FI": 18, "SE": 24, "NO": 15, "DK": 18, "IE": 22, "PT": 25, "GR": 27,
    "CY": 28, "MT": 31, "LU": 20, "UA": 29, "MD": 24, "GE": 22, "TR": 26,
}


def _alnum_span(raw: str, count: int) -> int:
    """Length of the prefix of ``raw`` that holds ``count`` letters/digits."""
    seen = 0
    for index, char in enumerate(raw):
        if char.isalnum():
            seen += 1
            if seen == count:
                return index + 1
    return len(raw)


def find_accounts(text: str) -> list[tuple[str, tuple[int, int]]]:
    """Valid bank accounts (IBAN, Polish NRB as ``PL`` IBAN) with their text spans."""
    found: list[tuple[str, tuple[int, int]]] = []
    upper = text.upper()
    for match in _IBAN_RE.finditer(upper):
        # The pattern may run into the next words ("... 2874 DO JUTRA"): cut the
        # candidate at the country's IBAN length, or try the longest valid prefix.
        compact = re.sub(r"[ \-]", "", match.group(0))
        country = compact[:2]
        lengths = ([_IBAN_LENGTHS[country]] if country in _IBAN_LENGTHS
                   else range(min(34, len(compact)), 14, -1))
        for length in lengths:
            candidate = compact[:length]
            if len(candidate) == length and _valid_iban(candidate):
                end = match.start() + _alnum_span(match.group(0), length)
                found.append((candidate, (match.start(), end)))
                break
    for match in _NRB_RE.finditer(upper):
        if any(start <= match.start() < end for _, (start, end) in found):
            continue
        compact = "PL" + re.sub(r"[ \-]", "", match.group(0))
        if _valid_iban(compact):
            found.append((compact, match.span()))
    return found


def find_emails(text: str) -> list[tuple[str, tuple[int, int]]]:
    return [(m.group(0).lower(), m.span()) for m in _EMAIL_RE.finditer(text)]


def find_phones(text: str, *, skip: list[tuple[int, int]] = ()) -> list[tuple[str, tuple[int, int]]]:
    """Phone-like digit groups of 9-15 digits outside the given spans (accounts, e-mails)."""
    found = []
    for match in _PHONE_RE.finditer(text):
        if any(start < match.end() and match.start() < end for start, end in skip):
            continue
        digits = norm_phone_digits(match.group(0))
        if len(digits) in _PHONE_DIGITS:
            found.append((digits, match.span()))
    return found


def mask_identifiers(text: str) -> str:
    """Mask accounts, e-mails, phone numbers and handles inside display text."""
    spans: list[tuple[int, int, str]] = []
    accounts = find_accounts(text)
    emails = find_emails(text)
    spans += [(s, e, f"{value[:4]} **** {value[-4:]}") for value, (s, e) in accounts]
    spans += [(s, e, _mask_email(value)) for value, (s, e) in emails]
    taken = [span for _, span in accounts + emails]
    spans += [(s, e, _mask_digits(value)) for value, (s, e) in find_phones(text, skip=taken)]
    for match in _TG_RE.finditer(text):
        if not any(s < match.end() and match.start() < e for s, e, _ in spans):
            spans.append((match.start(), match.end(), _mask_handle(match.group(1))))
    for start, end, replacement in sorted(spans, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text


def _text_evidence(text: str, *, artifact_id: str, funnel_step: int | None,
                   salt: str) -> list[Evidence]:
    """Contact identifiers (accounts) and long sentences from visible or pasted text."""
    out: list[Evidence] = []
    aid, step = artifact_id, funnel_step
    accounts = find_accounts(text)
    emails = find_emails(text)
    for value, _ in accounts:
        out.append(
            make_evidence(
                type="iban",
                tier=EvidenceTier.A,
                family=None,
                raw_value=value,
                display=f"{value[:4]} **** {value[-4:]}",
                artifact_id=aid,
                funnel_step=step,
                salt=salt,
            )
        )
    for value, _ in emails:
        out.append(_email_evidence(value, artifact_id=aid, funnel_step=step, salt=salt))
    for digits, _ in find_phones(text, skip=[span for _, span in accounts + emails]):
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
                display=sentence_display(sentence),
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


# Standard marketing / ad-platform parameters appear on unrelated sites.
_GENERIC_PARAMS = {"fbclid", "gclid", "gbraid", "wbraid", "dclid", "msclkid", "ttclid", "twclid",
                   "yclid", "li_fat_id", "igshid", "mc_cid", "mc_eid", "_ga", "_gl", "ref", "lang"}


def kit_param_names(url: str) -> set[str]:
    """Query parameter names that can characterise a kit (no utm_* or click IDs)."""
    return {name for name in param_name_set(url)
            if name and not name.startswith("utm_") and name not in _GENERIC_PARAMS}


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
    names = kit_param_names(url)
    if with_params and len(names) >= 2:
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
                    display=sentence_display(sentence),
                    artifact_id=artifact.id,
                    funnel_step=artifact.funnel_step,
                    salt=salt,
                )
            )
    return out


def sentence_display(sentence: str) -> str:
    """First 12 words of a sentence with identifiers masked (never raw accounts)."""
    words = mask_identifiers(" ".join(sentence.split())).split()
    return " ".join(words[:12]) + ("…" if len(words) > 12 else "")


def _email_evidence(value: str, *, artifact_id: str | None, funnel_step: int | None,
                    salt: str) -> Evidence:
    return make_evidence(
        type="email",
        tier=EvidenceTier.A,
        family=None,
        raw_value=value,
        display=_mask_email(value),
        artifact_id=artifact_id,
        funnel_step=funnel_step,
        host=value.rsplit("@", 1)[-1],
        salt=salt,
    )


def _mask_email(value: str) -> str:
    """``ab…@domain`` — the mailbox is masked, the domain stays readable."""
    local, _, domain = value.partition("@")
    return f"{local[:2]}…@{domain}" if len(local) > 2 else f"…@{domain}"


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
