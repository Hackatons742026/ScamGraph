"""Artifact / media deduplication — exact collapse + variant links."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from backend.pipeline.models import Artifact, MediaRef


@dataclass
class DedupRecord:
    """Canonical artifact after collapsing exact duplicates."""

    artifact: Artifact
    observations: int = 1
    duplicate_ids: list[str] = field(default_factory=list)
    variant_ids: list[str] = field(default_factory=list)


def content_sha256(path: str | Path) -> str | None:
    try:
        data = Path(path).read_bytes()
    except OSError:
        return None
    return hashlib.sha256(data).hexdigest()


def dedupe_artifacts(artifacts: list[Artifact]) -> list[DedupRecord]:
    """Collapse exact duplicates (same sha256 / identical path bytes).

    Variants (near-duplicates) are linked, not merged: same kind + same
    basename but different digest → listed under ``variant_ids``.
    """
    by_hash: dict[str, DedupRecord] = {}
    no_hash: list[DedupRecord] = []
    basename_index: dict[tuple[str, str], list[DedupRecord]] = {}

    for art in artifacts:
        digest = art.sha256 or content_sha256(art.path)
        if digest:
            art.sha256 = digest
            if digest in by_hash:
                rec = by_hash[digest]
                rec.observations += 1
                rec.duplicate_ids.append(art.id)
                continue
            rec = DedupRecord(artifact=art, observations=1)
            by_hash[digest] = rec
            key = (_kind(art), Path(art.path).name.lower())
            basename_index.setdefault(key, []).append(rec)
        else:
            rec = DedupRecord(artifact=art, observations=1)
            no_hash.append(rec)
            key = (_kind(art), Path(art.path).name.lower())
            basename_index.setdefault(key, []).append(rec)

    # Link variants: same kind+basename, different digests.
    for group in basename_index.values():
        if len(group) < 2:
            continue
        ids = [g.artifact.id for g in group]
        for rec in group:
            rec.variant_ids = [i for i in ids if i != rec.artifact.id]

    return list(by_hash.values()) + no_hash


def dedupe_media(media: list[MediaRef]) -> list[MediaRef]:
    """Collapse media with identical sha256; keep first, bump nothing (list unique)."""
    seen: set[str] = set()
    out: list[MediaRef] = []
    for item in media:
        if item.sha256 in seen:
            continue
        seen.add(item.sha256)
        out.append(item)
    return out


def _kind(art: Artifact) -> str:
    return art.kind.value if hasattr(art.kind, "value") else str(art.kind)
