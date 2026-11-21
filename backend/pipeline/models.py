"""Shared pipeline dataclasses (owned by ingest / cursor-backend).

Changes to these types must be published as an ``api_change`` ledger entry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ArtifactKind(str, Enum):
    """Detected artifact kinds (9 dataset types + classify helpers)."""

    HAR = "har"
    HTML = "html"
    MHTML = "mhtml"
    BUNDLE = "bundle"
    IMAGE = "image"
    VIDEO = "video"
    ADLIB_JSON = "adlib_json"
    TEXT = "text"
    URL = "url"
    UNKNOWN = "unknown"


class ParseStatus(str, Enum):
    OK = "ok"
    PARTIAL = "partial"
    FAILED = "failed"


class EvidenceTier(str, Enum):
    A = "A"
    B = "B"
    C = "C"


class EvidenceFamily(str, Enum):
    """Tier-B families; empty/None for pure tier-A or unstructured C."""

    KIT = "kit"
    TDS = "tds"
    DOMAIN = "domain"
    CREATIVE = "creative"
    HOSTING = "hosting"


@dataclass
class Coverage:
    """Per-incident coverage of artifact / evidence kinds.

    ``kinds_present`` lists ArtifactKind values (or evidence type keys) that
    were successfully observed. ``kinds_missing`` lists expected-but-absent
    kinds used for UI badges (e.g. ``no HAR``, ``video only``).
    """

    kinds_present: list[str] = field(default_factory=list)
    kinds_missing: list[str] = field(default_factory=list)
    artifact_counts: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kinds_present": list(self.kinds_present),
            "kinds_missing": list(self.kinds_missing),
            "artifact_counts": dict(self.artifact_counts),
            "notes": list(self.notes),
        }


@dataclass
class Evidence:
    """One typed evidence observation extracted from an artifact."""

    type: str
    tier: EvidenceTier | str
    family: EvidenceFamily | str | None
    value_hash: str
    display: str
    weight: float = 0.0
    artifact_id: str | None = None
    funnel_step: int | None = None
    ignored: bool = False
    ignore_reason: str | None = None


@dataclass
class Artifact:
    """One discovered (and later parsed) artifact file or bundle root."""

    id: str
    incident_id: str
    kind: ArtifactKind | str
    path: str
    funnel_step: int | None = None
    role: str | None = None
    sha256: str | None = None
    captured_at: datetime | None = None
    parser: str | None = None
    parse_status: ParseStatus | str | None = None
    error: str | None = None


@dataclass
class Incident:
    """One top-level incident folder (one reported case)."""

    id: str
    folder: str
    title: str | None = None
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    coverage: Coverage = field(default_factory=Coverage)
    status: str | None = None
    artifacts: list[Artifact] = field(default_factory=list)


@dataclass
class MediaRef:
    """Reference to a cached media object (frame / thumbnail / screenshot)."""

    id: str
    artifact_id: str
    kind: str
    sha256: str
    path: str | None = None
    phash: str | None = None
    frame_ts: float | None = None
    ocr_text: str | None = None


@dataclass
class IncidentBundle:
    """In-memory result of ``process_input`` — no DB writes.

    Used by classify (co-5) and by unit tests of the pipeline.
    """

    incident: Incident
    artifacts: list[Artifact] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    coverage: Coverage = field(default_factory=Coverage)
    media: list[MediaRef] = field(default_factory=list)
    source_paths: list[str] = field(default_factory=list)


# Funnel step index helpers (role assignment is deferred to in-4).
STRONA_PREFIX = "strona_"


def funnel_step_from_name(name: str) -> int | None:
    """Return 1-based funnel step index from a ``strona_N`` folder name."""
    lowered = name.lower().strip()
    if not lowered.startswith(STRONA_PREFIX):
        return None
    suffix = lowered[len(STRONA_PREFIX) :]
    if not suffix.isdigit():
        return None
    step = int(suffix)
    return step if step >= 1 else None
