"""Funnel role assignment (PDF §6.5) with ``strona_N`` order as fallback only."""

from __future__ import annotations

from dataclasses import dataclass

from backend.pipeline.intake.html import HtmlParseResult
from backend.pipeline.models import Artifact, ArtifactKind

FUNNEL_ROLES = ("ad", "prelander", "offer", "order")


@dataclass
class FunnelAssignment:
    artifact_id: str
    step: int | None
    role: str
    reason: str


def assign_funnel_roles(
    artifacts: list[Artifact],
    *,
    html_by_artifact: dict[str, HtmlParseResult] | None = None,
) -> list[FunnelAssignment]:
    """Assign ad / prelander / offer / order roles using content rules first.

    Fallback when content is inconclusive: map ``funnel_step`` 1..4 to the
    canonical order (and clamp higher steps to ``order``).
    """
    html_by_artifact = html_by_artifact or {}
    out: list[FunnelAssignment] = []
    for art in artifacts:
        role, reason = _role_for(art, html_by_artifact.get(art.id))
        out.append(
            FunnelAssignment(
                artifact_id=art.id,
                step=art.funnel_step,
                role=role,
                reason=reason,
            )
        )
    return out


def _role_for(art: Artifact, html: HtmlParseResult | None) -> tuple[str, str]:
    kind = art.kind.value if isinstance(art.kind, ArtifactKind) else str(art.kind)

    # Content rules from §6.5
    if kind in {ArtifactKind.IMAGE.value, ArtifactKind.VIDEO.value, ArtifactKind.ADLIB_JSON.value}:
        return "ad", f"artifact kind {kind}"

    if html is not None:
        text = (html.visible_text or "").lower()
        title = (html.title or "").lower()
        field_names = [n.lower() for f in html.forms for n in f.field_names]
        actions = " ".join((f.action_redacted or "") for f in html.forms).lower()

        personal = {"phone", "email", "name", "imie", "nazwisko", "telefon", "address"}
        if html.forms and (
            personal.intersection(field_names)
            or any(token in actions for token in ("order", "lead", "checkout", "api/v1"))
        ):
            return "order", "form with personal/lead fields or order endpoint"

        if any(token in text for token in ("zł", "pln", "price", "cena", "buy", "kup", "inwest")) or (
            "offer" in title
        ):
            return "offer", "price/offer language"

        if html.links and (
            "article" in title
            or len(text) > 400
            or any(token in text for token in ("quiz", "kliknij", "czytaj", "news"))
        ):
            return "prelander", "article/quiz structure with CTA links"

    # Folder-order fallback
    step = art.funnel_step
    if step is not None:
        if step <= 1:
            return "ad", "strona_N fallback step 1"
        if step == 2:
            return "prelander", "strona_N fallback step 2"
        if step == 3:
            return "offer", "strona_N fallback step 3"
        return "order", "strona_N fallback step >=4"

    if kind in {ArtifactKind.HTML.value, ArtifactKind.MHTML.value, ArtifactKind.BUNDLE.value}:
        return "offer", "default page role"
    return "unknown", "no content signals"
