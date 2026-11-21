"""Incident / artifact discovery over a dataset directory tree.

Each top-level folder under the data root is one incident. Artifact kind is
detected by content + extension (never by hard-coded incident IDs).
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from backend.pipeline.models import (
    Artifact,
    ArtifactKind,
    Coverage,
    Incident,
    funnel_step_from_name,
)

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm"}
HTML_SUFFIXES = {".html", ".htm"}
BUNDLE_MEMBER_NAMES = {"manifest.json", "dom.html", "page.har"}


def discover_incidents(data_dir: Path | str) -> list[Incident]:
    """Walk ``data_dir`` and return one :class:`Incident` per top-level folder."""
    root = Path(data_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"data dir not found: {root}")

    incidents: list[Incident] = []
    for child in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        incidents.append(_discover_incident(child))
    return incidents


def detect_artifact_kind(path: Path) -> ArtifactKind | None:
    """Detect artifact kind from extension + light content sniffing."""
    if path.is_dir():
        if (path / "manifest.json").is_file():
            return ArtifactKind.BUNDLE
        return None

    name = path.name
    suffix = path.suffix.lower()

    if name == ".har" or suffix == ".har":
        return ArtifactKind.HAR

    if name.endswith(".info.json"):
        return ArtifactKind.ADLIB_JSON

    if suffix in {".mhtml", ".mht"}:
        return ArtifactKind.MHTML

    if suffix in IMAGE_SUFFIXES:
        return ArtifactKind.IMAGE

    if suffix in VIDEO_SUFFIXES:
        return ArtifactKind.VIDEO

    if suffix in HTML_SUFFIXES:
        if name.lower() == "dom.html" and (path.parent / "manifest.json").is_file():
            return None
        return ArtifactKind.HTML

    return None


def _discover_incident(folder: Path) -> Incident:
    incident_id = _stable_id("inc", folder.name)
    artifacts = _scan_folder(folder, incident_id, funnel_step=None)
    return Incident(
        id=incident_id,
        folder=str(folder.resolve()),
        title=folder.name,
        coverage=_coverage_from_artifacts(artifacts),
        artifacts=artifacts,
    )


def _scan_folder(
    folder: Path,
    incident_id: str,
    funnel_step: int | None,
) -> list[Artifact]:
    artifacts: list[Artifact] = []

    # 1) Funnel steps recurse with their step index.
    for child in sorted(folder.iterdir(), key=lambda p: p.name.lower()):
        if child.is_dir():
            step = funnel_step_from_name(child.name)
            if step is not None:
                artifacts.extend(_scan_folder(child, incident_id, funnel_step=step))

    # 2) Capture-bundle directories (have manifest.json).
    bundle_roots: set[Path] = set()
    for child in sorted(folder.iterdir(), key=lambda p: p.name.lower()):
        if not child.is_dir():
            continue
        if funnel_step_from_name(child.name) is not None:
            continue
        if (child / "manifest.json").is_file():
            bundle_roots.add(child.resolve())
            artifacts.append(
                _make_artifact(incident_id, ArtifactKind.BUNDLE, child, funnel_step)
            )

    # Bundle rooted at this folder itself.
    if (folder / "manifest.json").is_file():
        bundle_roots.add(folder.resolve())
        artifacts.append(
            _make_artifact(incident_id, ArtifactKind.BUNDLE, folder, funnel_step)
        )

    # 3) Files in this folder (non-recursive), plus nested hidden ``.har``.
    for path in sorted(folder.iterdir(), key=lambda p: p.name.lower()):
        if path.is_dir():
            continue
        if _is_inside_any(path, bundle_roots):
            continue
        if path.name in BUNDLE_MEMBER_NAMES and (folder / "manifest.json").is_file():
            continue
        kind = detect_artifact_kind(path)
        if kind is None:
            continue
        artifacts.append(_make_artifact(incident_id, kind, path, funnel_step))

    # Nested hidden .har (and only .har) under non-funnel, non-bundle, non-_files dirs.
    for path in sorted(folder.rglob(".har")):
        if not path.is_file():
            continue
        if path.parent.resolve() == folder.resolve():
            continue  # already seen as a direct child
        if _relative_has_funnel(folder, path) and funnel_step is None:
            continue  # owned by the funnel recursion
        if _is_inside_any(path, bundle_roots):
            continue
        if _under_sidecar_dir(folder, path):
            continue
        artifacts.append(
            _make_artifact(incident_id, ArtifactKind.HAR, path, funnel_step)
        )

    # Saved-page HTML that lives next to a ``*_files`` directory is already
    # picked up as a direct child; also accept HTML one level down only when
    # paired with ``*_files`` and not inside a bundle/funnel.
    for path in sorted(folder.glob("*.html")) + sorted(folder.glob("*.htm")):
        # already handled in direct children loop
        _ = path

    return _dedupe_artifacts(artifacts)


def _make_artifact(
    incident_id: str,
    kind: ArtifactKind,
    path: Path,
    funnel_step: int | None,
) -> Artifact:
    resolved = str(path.resolve())
    return Artifact(
        id=_stable_id("art", f"{incident_id}:{kind.value}:{resolved}"),
        incident_id=incident_id,
        kind=kind,
        path=resolved,
        funnel_step=funnel_step,
    )


def _coverage_from_artifacts(artifacts: list[Artifact]) -> Coverage:
    counts: dict[str, int] = {}
    for art in artifacts:
        key = art.kind.value if isinstance(art.kind, ArtifactKind) else str(art.kind)
        counts[key] = counts.get(key, 0) + 1
    present = sorted(counts)
    expected = [
        ArtifactKind.HAR.value,
        ArtifactKind.HTML.value,
        ArtifactKind.MHTML.value,
        ArtifactKind.BUNDLE.value,
        ArtifactKind.IMAGE.value,
        ArtifactKind.VIDEO.value,
        ArtifactKind.ADLIB_JSON.value,
    ]
    return Coverage(
        kinds_present=present,
        kinds_missing=[k for k in expected if k not in counts],
        artifact_counts=counts,
    )


def _stable_id(prefix: str, material: str) -> str:
    return f"{prefix}_{uuid.uuid5(uuid.NAMESPACE_URL, material).hex[:12]}"


def _is_inside_any(path: Path, roots: set[Path]) -> bool:
    resolved = path.resolve()
    for root in roots:
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def _relative_has_funnel(folder: Path, path: Path) -> bool:
    try:
        parts = path.relative_to(folder).parts[:-1]
    except ValueError:
        return False
    return any(funnel_step_from_name(part) for part in parts)


def _under_sidecar_dir(folder: Path, path: Path) -> bool:
    try:
        parts = path.relative_to(folder).parts[:-1]
    except ValueError:
        return False
    return any(part.endswith("_files") or part in {"resources", "__MACOSX"} for part in parts)


def _dedupe_artifacts(artifacts: list[Artifact]) -> list[Artifact]:
    seen: set[str] = set()
    out: list[Artifact] = []
    for art in artifacts:
        key = f"{art.kind}:{art.path}:{art.funnel_step}"
        if key in seen:
            continue
        seen.add(key)
        out.append(art)
    return out


def looks_like_adlib(path: Path) -> bool:
    """Optional content check for Ad Library JSON (used by tests / later parsers)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    extractor = str(data.get("extractor", "")).lower()
    if "facebook" in extractor and "ad" in extractor:
        return True
    return any(k in data for k in ("ad_id", "ad_archive_id", "page_id", "advertiser"))
