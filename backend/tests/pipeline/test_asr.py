"""ASR soft-fail + tier-C transcript evidence (no real model / network)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.pipeline.asr import AsrResult, faster_whisper_available, transcribe_audio
from backend.pipeline.models import ArtifactKind, EvidenceTier, ParseStatus
from backend.pipeline.run import process_input, run_on_data_dir
from backend.pipeline.video import VideoParseResult


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SCAMGRAPH_SALT", "unit-test-salt")
    monkeypatch.setenv("SCAMGRAPH_CACHE_DIR", str(tmp_path / "cache"))
    # Default: ASR on unless a test disables it.
    monkeypatch.setenv("SCAMGRAPH_ASR", "1")


def _fake_wav(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Minimal non-empty file; decoding is mocked away.
    path.write_bytes(b"RIFF____WAVEfmt ")
    return path


def test_asr_soft_fails_when_faster_whisper_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "backend.pipeline.asr.faster_whisper_available", lambda: False
    )
    result = transcribe_audio(_fake_wav(tmp_path / "clip.wav"))
    assert result.text == ""
    assert result.engine is None
    assert result.error
    assert "faster-whisper" in result.error


def test_asr_soft_fails_when_disabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SCAMGRAPH_ASR", "0")
    monkeypatch.setattr(
        "backend.pipeline.asr.faster_whisper_available", lambda: True
    )
    result = transcribe_audio(_fake_wav(tmp_path / "clip.wav"))
    assert result.text == ""
    assert result.error
    assert "disabled" in result.error.lower() or "SCAMGRAPH_ASR" in (result.error or "")


def test_asr_mocked_whisper_returns_transcript(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "backend.pipeline.asr.faster_whisper_available", lambda: True
    )

    class _FakeModel:
        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
            assert kwargs.get("local_files_only") is True
            self._kwargs = kwargs

        def transcribe(self, _path, **_kwargs):  # noqa: ANN001, ANN003
            segs = [
                SimpleNamespace(
                    text="Jeden dwa trzy cztery piec szesc siedem osiem dziewiec dziesiec."
                )
            ]
            return segs, SimpleNamespace(language="pl")

    import sys
    import types

    fake_fw = types.ModuleType("faster_whisper")
    fake_fw.WhisperModel = _FakeModel  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_fw)

    result = transcribe_audio(_fake_wav(tmp_path / "speech.wav"), language="pl")
    assert result.engine == "faster-whisper"
    assert result.model == "small"
    assert result.error is None
    assert "dziesiec" in result.text
    assert len(result.text.split()) >= 10


def test_asr_model_init_failure_soft_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "backend.pipeline.asr.faster_whisper_available", lambda: True
    )

    class _BoomModel:
        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
            raise RuntimeError("no local model files")

    import sys
    import types

    fake_fw = types.ModuleType("faster_whisper")
    fake_fw.WhisperModel = _BoomModel  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_fw)

    result = transcribe_audio(_fake_wav(tmp_path / "speech.wav"))
    assert result.text == ""
    assert result.error
    assert result.engine == "faster-whisper"


def test_run_continues_when_asr_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "backend.pipeline.asr.faster_whisper_available", lambda: False
    )
    monkeypatch.setattr(
        "backend.pipeline.run.extract_keyframes",
        lambda *_a, **_k: VideoParseResult(ok=False, error="ffmpeg not available"),
    )
    root = tmp_path / "raw" / "inc_vid"
    root.mkdir(parents=True)
    (root / "clip.mp4").write_bytes(b"not-a-real-mp4")
    summary = run_on_data_dir(tmp_path / "raw", db_path=tmp_path / "t.db", persist=False)
    assert summary["ok"] == 1
    assert not summary["errors"]


def test_run_video_asr_emits_tier_c_shared_sentence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    transcript = (
        "To jest syntetyczny zapis mowy z wystarczajaca liczba slow "
        "dla tier C shared sentence."
    )
    assert len(transcript.split()) >= 10

    monkeypatch.setattr(
        "backend.pipeline.run.extract_keyframes",
        lambda *_a, **_k: VideoParseResult(ok=True, frames=[]),
    )
    monkeypatch.setattr(
        "backend.pipeline.run.transcribe_audio",
        lambda *_a, **_k: AsrResult(
            text=transcript,
            engine="faster-whisper",
            model="small",
        ),
    )

    clip = tmp_path / "upload" / "ad.mp4"
    clip.parent.mkdir(parents=True)
    clip.write_bytes(b"fake-mp4")
    bundle = process_input(paths=[clip])
    kinds = {
        a.kind.value if isinstance(a.kind, ArtifactKind) else str(a.kind)
        for a in bundle.artifacts
    }
    assert ArtifactKind.VIDEO.value in kinds

    tier_c = [
        e
        for e in bundle.evidence
        if e.type == "shared_sentence"
        and (
            e.tier == EvidenceTier.C
            or e.tier == "C"
            or getattr(e.tier, "value", None) == "C"
        )
    ]
    assert tier_c, "expected tier-C shared_sentence from ASR transcript"
    assert tier_c[0].family is None
    assert tier_c[0].value_hash
    # Display matches extractors: first ≤12 words (+ optional ellipsis).
    assert "…" not in tier_c[0].display or len(tier_c[0].display.split()) <= 13


def test_run_asr_soft_fail_leaves_evidence_without_transcript(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "backend.pipeline.run.extract_keyframes",
        lambda *_a, **_k: VideoParseResult(ok=True, frames=[]),
    )
    monkeypatch.setattr(
        "backend.pipeline.run.transcribe_audio",
        lambda *_a, **_k: AsrResult(text="", engine=None, error="model missing"),
    )
    clip = tmp_path / "upload" / "ad.mp4"
    clip.parent.mkdir(parents=True)
    clip.write_bytes(b"fake-mp4")
    bundle = process_input(paths=[clip])
    assert not any(e.type == "shared_sentence" for e in bundle.evidence)


def test_short_transcript_emits_no_evidence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "backend.pipeline.run.extract_keyframes",
        lambda *_a, **_k: VideoParseResult(ok=True, frames=[]),
    )
    monkeypatch.setattr(
        "backend.pipeline.run.transcribe_audio",
        lambda *_a, **_k: AsrResult(
            text="za krotko.",
            engine="faster-whisper",
            model="small",
        ),
    )
    clip = tmp_path / "upload" / "short.mp4"
    clip.parent.mkdir(parents=True)
    clip.write_bytes(b"fake-mp4")
    bundle = process_input(paths=[clip])
    assert not any(e.type == "shared_sentence" for e in bundle.evidence)


def test_asr_import_explosion_leaves_video_non_failed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "backend.pipeline.run.extract_keyframes",
        lambda *_a, **_k: VideoParseResult(ok=True, frames=[]),
    )

    def _boom(*_a, **_k):  # noqa: ANN001, ANN003
        raise OSError("broken faster-whisper wheel / DLL load failed")

    monkeypatch.setattr("backend.pipeline.run.transcribe_audio", _boom)
    # Also ensure the real helper never raises when availability explodes.
    monkeypatch.setattr(
        "backend.pipeline.asr.faster_whisper_available",
        lambda: (_ for _ in ()).throw(RuntimeError("import side-effect boom")),
    )
    soft = transcribe_audio(_fake_wav(tmp_path / "x.wav"))
    assert soft.text == ""
    assert soft.error

    clip = tmp_path / "upload" / "ad.mp4"
    clip.parent.mkdir(parents=True)
    clip.write_bytes(b"fake-mp4")
    bundle = process_input(paths=[clip])
    videos = [
        a
        for a in bundle.artifacts
        if (a.kind.value if isinstance(a.kind, ArtifactKind) else str(a.kind))
        == ArtifactKind.VIDEO.value
    ]
    assert videos
    assert videos[0].parse_status != ParseStatus.FAILED
    assert videos[0].parse_status == ParseStatus.OK
    assert not any(e.type == "shared_sentence" for e in bundle.evidence)


def test_asr_skips_oversized_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SCAMGRAPH_ASR_MAX_BYTES", "8")
    monkeypatch.setattr(
        "backend.pipeline.asr.faster_whisper_available", lambda: True
    )
    path = _fake_wav(tmp_path / "big.wav")
    path.write_bytes(b"0123456789abcdef")  # 16 bytes > 8
    result = transcribe_audio(path)
    assert result.text == ""
    assert result.error
    assert "too large" in result.error


def test_faster_whisper_available_does_not_import_torch_at_module_level() -> None:
    # Importing asr must not require torch; availability is lazy.
    import backend.pipeline.asr as asr_mod

    assert hasattr(asr_mod, "faster_whisper_available")
    # Calling the helper is fine either way; it must not raise.
    assert isinstance(faster_whisper_available(), bool)
