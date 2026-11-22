"""End-to-end ingestion: discover → parse → redact → extract → (optional) DB write.

Also exposes ``process_input`` for classify (no DB writes).
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from backend.pipeline.asr import transcribe_audio
from backend.pipeline.dedup import dedupe_artifacts, dedupe_media
from backend.pipeline.extract import ExtractInput, coverage_for, dedupe_evidence, extract_all
from backend.pipeline.extract.builders import make_evidence
from backend.pipeline.extract.extractors import _SENTENCE_RE
from backend.pipeline.extract.normalize import norm_text_sentence
from backend.pipeline.intake.adlib import parse_adlib
from backend.pipeline.intake.bundle import parse_bundle
from backend.pipeline.intake.discover import discover_incidents
from backend.pipeline.intake.funnel import assign_funnel_roles
from backend.pipeline.intake.har import parse_har
from backend.pipeline.intake.html import parse_html
from backend.pipeline.intake.image import parse_image
from backend.pipeline.intake.mhtml import parse_mhtml
from backend.pipeline.models import (
    Artifact,
    ArtifactKind,
    Evidence,
    EvidenceTier,
    Incident,
    IncidentBundle,
    MediaRef,
    ParseStatus,
)
from backend.pipeline.redact import counting_redactions, require_salt
from backend.pipeline.video import extract_keyframes

logger = logging.getLogger(__name__)


def process_input(
    paths: list[Path] | None = None,
    text: str | None = None,
    url: str | None = None,
) -> IncidentBundle:
    """Parse uploaded paths / text / URL into an in-memory bundle (no DB writes)."""
    require_salt()
    cache = Path(os.environ.get("SCAMGRAPH_CACHE_DIR") or "data/cache")
    batch = cache / "classify" / f"batch_{uuid.uuid4().hex[:10]}"
    incident_dir = batch / "classify_incident"
    incident_dir.mkdir(parents=True, exist_ok=True)

    for src in paths or []:
        src = Path(src)
        if not src.exists():
            continue
        dest = incident_dir / src.name
        if src.is_dir():
            shutil.copytree(src, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dest)

    if text:
        (incident_dir / "note.txt").write_text(text, encoding="utf-8")
    if url:
        (incident_dir / "url.txt").write_text(url.strip(), encoding="utf-8")

    discovered = discover_incidents(batch)
    if discovered:
        incident = discovered[0]
    else:
        incident = Incident(
            id=f"inc_{uuid.uuid4().hex[:12]}",
            folder=str(incident_dir.resolve()),
            title="classify_incident",
            artifacts=[],
        )

    # Typed text/url artifacts when present (discovery may miss .txt).
    extras: list[Artifact] = []
    note = incident_dir / "note.txt"
    url_file = incident_dir / "url.txt"
    known = {Path(a.path).name for a in incident.artifacts}
    if note.is_file() and "note.txt" not in known:
        extras.append(
            Artifact(
                id=f"art_{uuid.uuid4().hex[:12]}",
                incident_id=incident.id,
                kind=ArtifactKind.TEXT,
                path=str(note.resolve()),
                parse_status=ParseStatus.OK,
                parser="text",
            )
        )
    if url_file.is_file() and "url.txt" not in known:
        extras.append(
            Artifact(
                id=f"art_{uuid.uuid4().hex[:12]}",
                incident_id=incident.id,
                kind=ArtifactKind.URL,
                path=str(url_file.resolve()),
                parse_status=ParseStatus.OK,
                parser="url",
            )
        )
    incident.artifacts = list(incident.artifacts) + extras
    parsed = _parse_incident(incident)
    return IncidentBundle(
        incident=parsed["incident"],
        artifacts=parsed["artifacts"],
        evidence=parsed["evidence"],
        coverage=parsed["coverage"],
        media=parsed["media"],
        source_paths=[str(p) for p in (paths or [])],
    )


def run_on_data_dir(
    data_dir: Path | str,
    *,
    db_path: Path | str | None = None,
    persist: bool = True,
) -> dict:
    """Discover and process every incident under ``data_dir``."""
    require_salt()
    root = Path(data_dir)
    started = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    run_id = f"run_{started.strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:6]}"

    repo = None
    if persist:
        from backend.db.repository import Repository

        db = Path(db_path or os.environ.get("SCAMGRAPH_DB") or "data/scamgraph.db")
        repo = Repository(db)
        repo.save_run(run_id, "running", started.isoformat())

    incidents = discover_incidents(root)
    summaries: list[dict] = []
    errors: list[str] = []
    secrets_redacted = 0

    with counting_redactions() as redact_box:
        for incident in incidents:
            try:
                parsed = _parse_incident(incident)
                if repo is not None:
                    inc = parsed["incident"]
                    repo.save_incident(inc)
                    repo.save_artifacts(parsed["artifacts"])
                    repo.save_evidence(inc.id, parsed["evidence"])
                    if parsed["media"]:
                        repo.save_media(parsed["media"])
                summaries.append(
                    {
                        "incident_id": incident.id,
                        "artifacts": len(parsed["artifacts"]),
                        "evidence": len(parsed["evidence"]),
                        "media": len(parsed["media"]),
                    }
                )
            except Exception as exc:  # noqa: BLE001 — isolation boundary
                msg = f"{incident.id}: {type(exc).__name__}: {exc}"
                logger.exception("incident failed: %s", incident.id)
                errors.append(msg[:300])

    secrets_redacted = redact_box[0]
    elapsed = time.perf_counter() - t0
    finished = datetime.now(timezone.utc)
    summary = {
        "incidents": len(incidents),
        "ok": len(summaries),
        "errors": errors,
        "elapsed_s": round(elapsed, 3),
        "details": summaries,
        "run_id": run_id,
        "secrets_redacted": secrets_redacted,
    }
    if repo is not None:
        repo.save_run(
            run_id,
            "done",
            started.isoformat(),
            finished_at=finished.isoformat(),
            summary=summary,
            error="; ".join(errors)[:500] if errors else None,
        )
    return summary


def _parse_incident(incident: Incident) -> dict:
    deduped = dedupe_artifacts(list(incident.artifacts))
    artifacts = [d.artifact for d in deduped]
    observations_by_artifact = {rec.artifact.id: rec.observations for rec in deduped}

    har_map: dict = {}
    html_map: dict = {}
    adlib_map: dict = {}
    media_pairs: list[tuple[Artifact, MediaRef]] = []
    html_for_funnel: dict = {}
    asr_transcripts: list[tuple[Artifact, str]] = []

    for art in artifacts:
        kind = art.kind.value if isinstance(art.kind, ArtifactKind) else str(art.kind)
        try:
            if kind == ArtifactKind.HAR.value:
                result = parse_har(art.path)
                art.parser, art.parse_status, art.error = "har", result.parse_status, result.error
                har_map[art.id] = result
            elif kind == ArtifactKind.HTML.value:
                result = parse_html(art.path)
                art.parser, art.parse_status, art.error = "html", result.parse_status, result.error
                html_map[art.id] = result
                html_for_funnel[art.id] = result
            elif kind == ArtifactKind.MHTML.value:
                result = parse_mhtml(art.path)
                art.parser, art.parse_status, art.error = "mhtml", result.parse_status, result.error
                if result.html is not None:
                    html_map[art.id] = result.html
                    html_for_funnel[art.id] = result.html
            elif kind == ArtifactKind.BUNDLE.value:
                result = parse_bundle(art.path)
                art.parser, art.parse_status, art.error = "bundle", result.parse_status, result.error
                if result.html is not None:
                    html_map[art.id] = result.html
                    html_for_funnel[art.id] = result.html
                if result.har is not None:
                    har_map[art.id] = result.har
            elif kind == ArtifactKind.IMAGE.value:
                result = parse_image(art.path, artifact_id=art.id)
                art.parser, art.parse_status, art.error = "image", result.parse_status, result.error
                if result.media is not None:
                    media_pairs.append((art, result.media))
            elif kind == ArtifactKind.VIDEO.value:
                result = extract_keyframes(art.path, artifact_id=art.id)
                art.parser = "video"
                if result.ok:
                    art.parse_status = ParseStatus.OK
                    for frame in result.frames:
                        media_pairs.append((art, frame))
                else:
                    art.parse_status = ParseStatus.PARTIAL
                    art.error = result.error
                # Optional ASR — soft-fail; must not flip video parse_status to FAILED.
                try:
                    asr = transcribe_audio(art.path)
                    if asr.text.strip():
                        asr_transcripts.append((art, asr.text.strip()))
                    elif asr.error:
                        logger.info("ASR soft-fail %s: %s", art.id, asr.error)
                except Exception as asr_exc:  # noqa: BLE001 — belt-and-suspenders
                    logger.info("ASR soft-fail %s: %s", art.id, asr_exc)
            elif kind == ArtifactKind.ADLIB_JSON.value:
                result = parse_adlib(art.path)
                art.parser, art.parse_status, art.error = "adlib", result.parse_status, result.error
                adlib_map[art.id] = result
            elif kind in {ArtifactKind.TEXT.value, ArtifactKind.URL.value}:
                art.parser = kind
                art.parse_status = ParseStatus.OK
            else:
                art.parse_status = ParseStatus.PARTIAL
                art.error = f"unsupported kind {kind}"
        except Exception as exc:  # noqa: BLE001
            art.parse_status = ParseStatus.FAILED
            art.error = f"{type(exc).__name__}: {exc}"[:200]
            logger.exception("artifact parse failed: %s", art.path)

    # Parsers own `error`; add the observation count only after they have completed.
    # Keep the legacy persisted marker so older API consumers can read the count.
    for art in artifacts:
        observations = observations_by_artifact.get(art.id, 1)
        if observations > 1:
            marker = f"observations={observations}"
            art.error = f"{art.error}; {marker}" if art.error else marker

    role_by_id = {
        r.artifact_id: r.role
        for r in assign_funnel_roles(artifacts, html_by_artifact=html_for_funnel)
    }
    for art in artifacts:
        art.role = role_by_id.get(art.id, art.role)

    salt = require_salt()
    extracted = extract_all(
        ExtractInput(
            incident_id=incident.id,
            artifacts=artifacts,
            har=har_map,
            html=html_map,
            adlib=adlib_map,
            media=media_pairs,
        ),
        salt=salt,
    )
    evidence = list(extracted.evidence)
    for art, transcript in asr_transcripts:
        evidence.extend(_evidence_from_transcript(transcript, artifact=art, salt=salt))
    if asr_transcripts:
        evidence = dedupe_evidence(evidence)
    coverage = (
        coverage_for(artifacts, evidence) if asr_transcripts else extracted.coverage
    )
    media = dedupe_media([m for _, m in media_pairs])
    incident.artifacts = artifacts
    incident.coverage = coverage
    return {
        "incident": incident,
        "artifacts": artifacts,
        "evidence": evidence,
        "coverage": coverage,
        "media": media,
    }


def _evidence_from_transcript(
    text: str,
    *,
    artifact: Artifact,
    salt: str,
) -> list[Evidence]:
    """Tier-C ``shared_sentence`` per sentence (≥10 words), same gate as extractors."""
    out: list[Evidence] = []
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
                artifact_id=artifact.id,
                funnel_step=artifact.funnel_step,
                salt=salt,
            )
        )
    return out


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="ScamGraph DNA ingestion pipeline")
    parser.add_argument(
        "--data",
        default=os.environ.get("SCAMGRAPH_DATA_DIR", "data/raw"),
        help="Dataset root (each subfolder = one incident)",
    )
    parser.add_argument(
        "--db",
        default=os.environ.get("SCAMGRAPH_DB", "data/scamgraph.db"),
        help="SQLite database path",
    )
    parser.add_argument(
        "--no-persist",
        action="store_true",
        help="Parse/extract only; do not write the database",
    )
    args = parser.parse_args(argv)
    summary = run_on_data_dir(args.data, db_path=args.db, persist=not args.no_persist)
    print(
        f"run={summary['run_id']} incidents={summary['incidents']} "
        f"ok={summary['ok']} errors={len(summary['errors'])} "
        f"elapsed_s={summary['elapsed_s']}"
    )
    for err in summary["errors"]:
        print(f"ERROR {err}")
    return 1 if summary["errors"] and summary["ok"] == 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
