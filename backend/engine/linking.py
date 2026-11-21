"""Conservative, explainable evidence linking for incidents."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations
from math import log
import re
from typing import Iterable, Mapping, Sequence

from backend.pipeline.models import Evidence, EvidenceFamily, EvidenceTier


@dataclass(frozen=True)
class MatchedEvidence:
    type: str
    tier: str
    family: str | None
    display: str
    value_hash: str
    weight: float
    artifact_ids: tuple[str, ...]
    funnel_steps: tuple[int, ...]
    detail: str


@dataclass(frozen=True)
class LinkEdge:
    source: str
    target: str
    level: str
    tier: str
    families: tuple[str, ...]
    score: float
    comparable: int
    low_confidence: bool
    evidence: tuple[MatchedEvidence, ...]


def _value(value: object) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _placeholder_phone(display: str) -> bool:
    digits = "".join(re.findall(r"\d", display))
    if len(digits) < 6:
        return False
    if len(set(digits)) == 1:
        return True
    ascending = "01234567890123456789"
    descending = ascending[::-1]
    return digits in ascending or digits in descending


def _engine_ignored(evidence: Evidence) -> bool:
    """Apply cheap safety ignores in addition to pipeline annotations."""
    if evidence.ignored or evidence.ignore_reason:
        return True
    safe = evidence.display.casefold()
    if any(name in safe for name in ("jquery", "jsdelivr", "google fonts")):
        return True
    return evidence.type in {"phone", "phone_number"} and _placeholder_phone(safe)


def _index(
    incidents: Mapping[str, Sequence[Evidence]],
) -> tuple[dict[tuple[str, str], dict[str, list[Evidence]]], dict[str, int]]:
    by_value: dict[tuple[str, str], dict[str, list[Evidence]]] = defaultdict(
        lambda: defaultdict(list)
    )
    document_frequency: dict[str, set[str]] = defaultdict(set)
    for incident_id, rows in incidents.items():
        for evidence in rows:
            if _engine_ignored(evidence):
                continue
            key = (evidence.type, evidence.value_hash)
            by_value[key][incident_id].append(evidence)
            document_frequency[evidence.value_hash].add(incident_id)
    return by_value, {value: len(ids) for value, ids in document_frequency.items()}


def candidate_pairs(incidents: Mapping[str, Sequence[Evidence]]) -> set[tuple[str, str]]:
    """Generate pairs via an inverted index instead of an O(N²) scan."""
    by_value, _ = _index(incidents)
    pairs: set[tuple[str, str]] = set()
    for occurrences in by_value.values():
        pairs.update(combinations(sorted(occurrences), 2))
    return pairs


def _matched(
    left: Sequence[Evidence],
    right: Sequence[Evidence],
    *,
    incident_count: int,
    document_frequency: Mapping[str, int],
) -> list[MatchedEvidence]:
    right_by_key: dict[tuple[str, str], list[Evidence]] = defaultdict(list)
    for evidence in right:
        if not _engine_ignored(evidence):
            right_by_key[(evidence.type, evidence.value_hash)].append(evidence)

    matches: list[MatchedEvidence] = []
    seen: set[tuple[str, str]] = set()
    for evidence in left:
        key = (evidence.type, evidence.value_hash)
        if key in seen or _engine_ignored(evidence) or key not in right_by_key:
            continue
        seen.add(key)
        df = document_frequency.get(evidence.value_hash, 1)
        if df / incident_count > 0.30:
            continue
        peers = right_by_key[key]
        family = _value(evidence.family) if evidence.family is not None else None
        artifacts = {row.artifact_id for row in [evidence, *peers] if row.artifact_id}
        steps = {row.funnel_step for row in [evidence, *peers] if row.funnel_step is not None}
        matches.append(
            MatchedEvidence(
                type=evidence.type,
                tier=_value(evidence.tier),
                family=family,
                display=evidence.display,
                value_hash=evidence.value_hash,
                weight=log(incident_count / df),
                artifact_ids=tuple(sorted(artifacts)),
                funnel_steps=tuple(sorted(steps)),
                detail=f"exact hash match; df={df}/{incident_count}",
            )
        )
    return matches


def _creative_counts(matches: Sequence[MatchedEvidence]) -> bool:
    creative = [row for row in matches if row.family == EvidenceFamily.CREATIVE.value]
    near_ad = any(
        row.type in {"ad_creative", "ad_creative_phash", "near_identical_ad_creative"}
        for row in creative
    )
    return near_ad or len({row.value_hash for row in creative}) >= 3


def _edge(
    source: str,
    target: str,
    left: Sequence[Evidence],
    right: Sequence[Evidence],
    *,
    incident_count: int,
    document_frequency: Mapping[str, int],
) -> LinkEdge | None:
    left_types = {row.type for row in left if not _engine_ignored(row)}
    right_types = {row.type for row in right if not _engine_ignored(row)}
    comparable = len(left_types & right_types)
    matches = _matched(
        left,
        right,
        incident_count=incident_count,
        document_frequency=document_frequency,
    )
    if not matches:
        return None

    tier_a = any(row.tier == EvidenceTier.A.value for row in matches)
    b_families = {
        row.family for row in matches if row.tier == EvidenceTier.B.value and row.family
    }
    if EvidenceFamily.CREATIVE.value in b_families and not _creative_counts(matches):
        b_families.remove(EvidenceFamily.CREATIVE.value)
    c_types = {row.type for row in matches if row.tier == EvidenceTier.C.value}

    if tier_a or len(b_families) >= 2:
        level = "campaign"
    elif b_families or len(c_types) >= 2:
        level = "network"
    else:
        return None

    strongest = "A" if tier_a else "B" if b_families else "C"
    return LinkEdge(
        source=source,
        target=target,
        level=level,
        tier=strongest,
        families=tuple(sorted(b_families)),
        score=sum(row.weight for row in matches),
        comparable=comparable,
        low_confidence=comparable < 2,
        evidence=tuple(matches),
    )


def link_incidents(incidents: Mapping[str, Sequence[Evidence]]) -> list[LinkEdge]:
    """Return deterministic, evidence-backed links between incidents."""
    if len(incidents) < 2:
        return []
    _, document_frequency = _index(incidents)
    edges = []
    for source, target in sorted(candidate_pairs(incidents)):
        edge = _edge(
            source,
            target,
            incidents[source],
            incidents[target],
            incident_count=len(incidents),
            document_frequency=document_frequency,
        )
        if edge is not None:
            edges.append(edge)
    return edges
