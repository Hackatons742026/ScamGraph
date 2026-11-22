"""Ignore-list helpers — mark evidence ignored=true with ignore_reason."""

from __future__ import annotations

import ipaddress
import re

from backend.pipeline.extract.normalize import norm_host, norm_phone_digits

# Well-known public library / CDN host fragments.
_PUBLIC_LIB_HOST_FRAGMENTS = (
    "jquery",
    "jsdelivr",
    "cdnjs",
    "unpkg.com",
    "googleapis.com",
    "gstatic.com",
    "googletagmanager.com",
    "fonts.googleapis",
    "fonts.gstatic",
    "bootstrapcdn",
    "cloudflare.com",
    "akamai",
    "fastly",
)

# Large shared platforms that appear on unrelated pages (share buttons, app
# store badges, login widgets). A shared link to one of them is not operator
# infrastructure, so domain evidence on these hosts never creates an edge.
_PLATFORM_DOMAINS = (
    "google.com", "google.pl", "youtube.com", "youtu.be", "goo.gl",
    "googleadservices.com", "googlesyndication.com", "doubleclick.net",
    "google-analytics.com", "facebook.com", "facebook.net", "fb.com", "fb.me",
    "fbcdn.net", "instagram.com", "messenger.com", "whatsapp.com", "wa.me",
    "twitter.com", "x.com", "t.co", "tiktok.com", "linkedin.com", "pinterest.com",
    "reddit.com", "telegram.org", "t.me", "apple.com", "microsoft.com",
    "live.com", "bing.com", "yahoo.com", "wikipedia.org", "w3.org", "schema.org",
    "gravatar.com", "wordpress.org", "wp.com", "amazonaws.com", "cloudfront.net",
)
_PLATFORM_EVIDENCE_TYPES = {"landing_domain", "click_domain"}

# Simplified CDN / shared-hosting ranges (documentation / common edges).
_CDN_NETWORKS = [
    ipaddress.ip_network("103.21.244.0/22"),  # Cloudflare sample
    ipaddress.ip_network("103.22.200.0/22"),
    ipaddress.ip_network("103.31.4.0/22"),
    ipaddress.ip_network("104.16.0.0/13"),
    ipaddress.ip_network("108.162.192.0/18"),
    ipaddress.ip_network("141.101.64.0/18"),
    ipaddress.ip_network("162.158.0.0/15"),
    ipaddress.ip_network("172.64.0.0/13"),
    ipaddress.ip_network("173.245.48.0/20"),
    ipaddress.ip_network("188.114.96.0/20"),
    ipaddress.ip_network("190.93.240.0/20"),
    ipaddress.ip_network("197.234.240.0/22"),
    ipaddress.ip_network("198.41.128.0/17"),
]


def ignore_reason_for(
    *,
    evidence_type: str,
    display: str,
    value: str | None = None,
    host: str | None = None,
    ip: str | None = None,
    doc_bytes: int | None = None,
) -> str | None:
    """Return an ignore_reason or None if the evidence should count."""
    if evidence_type in {"dom_skeleton", "dom_skeleton_hash"} and doc_bytes is not None:
        if doc_bytes < 5 * 1024:
            return "small_doc"

    if ip:
        reason = _cdn_ip_reason(ip)
        if reason:
            return reason

    hay = " ".join(x for x in (display, value, host) if x).lower()
    if any(frag in hay for frag in _PUBLIC_LIB_HOST_FRAGMENTS):
        return "public_lib"
    if host and any(frag in norm_host(host) for frag in _PUBLIC_LIB_HOST_FRAGMENTS):
        return "public_lib"
    if evidence_type in _PLATFORM_EVIDENCE_TYPES and is_platform_domain(host or display):
        return "platform_domain"

    if evidence_type in {"phone", "phone_number"}:
        if _placeholder_phone(display) or (value and _placeholder_phone(value)):
            return "placeholder_phone"

    return None


def is_platform_domain(host: str | None) -> bool:
    """True when ``host`` is (a subdomain of) a large shared platform."""
    name = norm_host(host or "")
    return any(name == domain or name.endswith("." + domain) for domain in _PLATFORM_DOMAINS)


def is_third_party_host(host: str | None) -> bool:
    """Embedded widgets, trackers and public CDNs: never the funnel page itself."""
    if not host:
        return False
    name = norm_host(host)
    return is_platform_domain(name) or any(frag in name for frag in _PUBLIC_LIB_HOST_FRAGMENTS)


def _cdn_ip_reason(ip: str) -> str | None:
    try:
        addr = ipaddress.ip_address(ip.strip())
    except ValueError:
        return None
    for network in _CDN_NETWORKS:
        if addr in network:
            return "cdn_ip"
    return None


def _placeholder_phone(display: str) -> bool:
    digits = norm_phone_digits(display)
    if len(digits) < 6:
        return False
    if len(set(digits)) == 1:
        return True
    ascending = "01234567890123456789"
    descending = ascending[::-1]
    return digits in ascending or digits in descending
