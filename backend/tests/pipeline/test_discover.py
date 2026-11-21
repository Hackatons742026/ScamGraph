"""Discovery tests against the synthetic 9-type tree."""

from __future__ import annotations

from pathlib import Path

from backend.pipeline.intake.discover import detect_artifact_kind, discover_incidents
from backend.pipeline.models import ArtifactKind


def test_discover_all_nine_artifact_types(synthetic_dataset: Path) -> None:
    incidents = discover_incidents(synthetic_dataset)
    assert len(incidents) == 2

    alpha = next(i for i in incidents if i.title == "incident_alpha")
    kinds = {a.kind for a in alpha.artifacts}

    assert ArtifactKind.HAR in kinds
    assert ArtifactKind.HTML in kinds
    assert ArtifactKind.MHTML in kinds
    assert ArtifactKind.BUNDLE in kinds
    assert ArtifactKind.IMAGE in kinds
    assert ArtifactKind.VIDEO in kinds
    assert ArtifactKind.ADLIB_JSON in kinds

    # Hidden .har + top-level capture.har + funnel step har
    har_paths = [Path(a.path).name for a in alpha.artifacts if a.kind == ArtifactKind.HAR]
    assert ".har" in har_paths
    assert "capture.har" in har_paths
    assert "step1.har" in har_paths

    # Bundle is the directory, not its members
    bundles = [a for a in alpha.artifacts if a.kind == ArtifactKind.BUNDLE]
    assert len(bundles) == 1
    assert Path(bundles[0].path).name == "capture_bundle"
    member_names = {Path(a.path).name for a in alpha.artifacts}
    assert "dom.html" not in member_names
    assert "page.har" not in member_names
    assert "manifest.json" not in member_names


def test_funnel_step_indexes(synthetic_dataset: Path) -> None:
    alpha = next(i for i in discover_incidents(synthetic_dataset) if i.title == "incident_alpha")
    by_step: dict[int | None, list[str]] = {}
    for art in alpha.artifacts:
        by_step.setdefault(art.funnel_step, []).append(Path(art.path).name)

    assert any(name.endswith(".html") for name in by_step.get(1, []))
    assert any(name.endswith(".html") for name in by_step.get(2, []))
    assert any(name.endswith(".html") for name in by_step.get(3, []))
    # Top-level artifacts have no funnel step
    assert "capture.har" in by_step.get(None, [])
    assert "offer.html" in by_step.get(None, [])


def test_coverage_lists_present_kinds(synthetic_dataset: Path) -> None:
    alpha = next(i for i in discover_incidents(synthetic_dataset) if i.title == "incident_alpha")
    present = set(alpha.coverage.kinds_present)
    for kind in (
        "har",
        "html",
        "mhtml",
        "bundle",
        "image",
        "video",
        "adlib_json",
    ):
        assert kind in present
    assert alpha.coverage.artifact_counts["har"] >= 2


def test_sparse_second_incident(synthetic_dataset: Path) -> None:
    beta = next(i for i in discover_incidents(synthetic_dataset) if i.title == "incident_beta")
    assert len(beta.artifacts) == 1
    assert beta.artifacts[0].kind == ArtifactKind.IMAGE
    assert "har" in beta.coverage.kinds_missing


def test_detect_artifact_kind_helpers(tmp_path: Path) -> None:
    har = tmp_path / ".har"
    har.write_text("{}", encoding="utf-8")
    assert detect_artifact_kind(har) == ArtifactKind.HAR

    info = tmp_path / "x.info.json"
    info.write_text('{"extractor":"facebook:ads"}', encoding="utf-8")
    assert detect_artifact_kind(info) == ArtifactKind.ADLIB_JSON

    bundle = tmp_path / "b"
    bundle.mkdir()
    (bundle / "manifest.json").write_text("{}", encoding="utf-8")
    assert detect_artifact_kind(bundle) == ArtifactKind.BUNDLE
