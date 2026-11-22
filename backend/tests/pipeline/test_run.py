"""E2E pipeline run + process_input tests (synthetic dataset only)."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.pipeline.models import Artifact, ArtifactKind, Incident
from backend.pipeline.run import _parse_incident, process_input, run_on_data_dir
from backend.tests.fixtures.synthetic_har import write_har
from backend.tests.fixtures.synthetic_media import write_adlib, write_png
from backend.tests.fixtures.synthetic_pages import write_saved_page
from backend.tests.fixtures.synthetic_tree import build_synthetic_dataset


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SCAMGRAPH_SALT", "unit-test-salt")
    monkeypatch.setenv("SCAMGRAPH_CACHE_DIR", str(tmp_path / "cache"))


def test_run_on_synthetic_dataset_persists(tmp_path: Path) -> None:
    data = build_synthetic_dataset(tmp_path / "raw")
    db = tmp_path / "test.db"
    summary = run_on_data_dir(data, db_path=db, persist=True)
    assert summary["incidents"] == 2
    assert summary["ok"] >= 1
    assert summary["elapsed_s"] < 120
    assert db.is_file()

    from backend.db.repository import Repository

    repo = Repository(db)
    # At least one incident row exists
    assert summary["details"]
    first_id = summary["details"][0]["incident_id"]
    assert repo.get_incident(first_id) is not None
    assert repo.get_artifacts(first_id)
    assert repo.get_evidence(first_id)


def test_process_input_text_url_no_db(tmp_path: Path) -> None:
    page = write_saved_page(tmp_path / "upload")
    bundle = process_input(
        paths=[page.parent],
        text="synthetic classify note with enough words for coverage",
        url="https://land.example-scam.test/x",
    )
    assert bundle.incident.id
    kinds = {
        a.kind.value if isinstance(a.kind, ArtifactKind) else str(a.kind)
        for a in bundle.artifacts
    }
    assert ArtifactKind.HTML.value in kinds or ArtifactKind.TEXT.value in kinds
    assert bundle.coverage is not None


def test_same_batch_image_observation_count_survives_parser(tmp_path: Path) -> None:
    pytest.importorskip("PIL.Image")
    first = write_png(tmp_path / "first.png")
    second = tmp_path / "second.png"
    second.write_bytes(first.read_bytes())
    incident = Incident("synthetic-duplicates", str(tmp_path), artifacts=[
        Artifact("artifact-first", "synthetic-duplicates", ArtifactKind.IMAGE, str(first)),
        Artifact("artifact-second", "synthetic-duplicates", ArtifactKind.IMAGE, str(second)),
    ])

    parsed = _parse_incident(incident)

    assert len(parsed["artifacts"]) == 1
    assert parsed["artifacts"][0].sha256
    assert parsed["artifacts"][0].error and parsed["artifacts"][0].error.endswith("observations=2")


def test_run_continues_after_broken_artifact(tmp_path: Path) -> None:
    root = tmp_path / "raw" / "one"
    root.mkdir(parents=True)
    write_png(root / "ok.png")
    (root / "broken.har").write_text("{not-json", encoding="utf-8")
    write_adlib(root / "ad.info.json")
    summary = run_on_data_dir(tmp_path / "raw", db_path=tmp_path / "t.db", persist=True)
    assert summary["ok"] == 1


def test_run_summary_counts_secrets_redacted_from_har(tmp_path: Path) -> None:
    root = tmp_path / "raw" / "har-case"
    root.mkdir(parents=True)
    write_har(root / "traffic.har")
    summary = run_on_data_dir(tmp_path / "raw", db_path=tmp_path / "t.db", persist=True)
    assert summary["ok"] == 1
    assert summary["secrets_redacted"] > 0
