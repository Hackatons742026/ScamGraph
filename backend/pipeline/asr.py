"""Optional speech-to-text via faster-whisper (soft-fail, offline)."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_MODEL_SIZE = "small"
_AUDIO_EXTS = {".wav", ".mp3", ".flac", ".m4a", ".ogg", ".opus", ".aac"}
# Soft guards — avoid hanging the pipeline on huge clips / stuck inference.
_DEFAULT_MAX_BYTES = 50 * 1024 * 1024  # 50 MiB
_DEFAULT_TIMEOUT_S = 120


@dataclass
class AsrResult:
    text: str
    engine: str | None  # "faster-whisper" when used
    error: str | None = None
    model: str | None = None  # "small"


def asr_enabled() -> bool:
    """``SCAMGRAPH_ASR=0`` disables ASR (soft skip)."""
    raw = (os.environ.get("SCAMGRAPH_ASR") or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def faster_whisper_available() -> bool:
    try:
        import faster_whisper  # noqa: F401

        return True
    except Exception:  # noqa: BLE001 — broken optional installs must soft-fail
        return False


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _max_bytes() -> int:
    raw = os.environ.get("SCAMGRAPH_ASR_MAX_BYTES")
    if raw is None or not raw.strip():
        return _DEFAULT_MAX_BYTES
    try:
        return max(0, int(raw))
    except ValueError:
        return _DEFAULT_MAX_BYTES


def _timeout_s() -> int:
    raw = os.environ.get("SCAMGRAPH_ASR_TIMEOUT")
    if raw is None or not raw.strip():
        return _DEFAULT_TIMEOUT_S
    try:
        return max(1, int(raw))
    except ValueError:
        return _DEFAULT_TIMEOUT_S


def transcribe_audio(path: Path | str, *, language: str | None = "pl") -> AsrResult:
    """Transcribe audio/video with faster-whisper ``small``. Never raises.

    Offline: ``local_files_only=True`` — missing model files soft-fail.
    Broken optional installs, import explosions, and timeouts all soft-fail.
    """
    try:
        return _transcribe_audio_inner(path, language=language)
    except Exception as exc:  # noqa: BLE001
        logger.info("ASR soft-fail: %s", exc)
        return AsrResult(text="", engine=None, error=str(exc)[:200])


def _transcribe_audio_inner(path: Path | str, *, language: str | None) -> AsrResult:
    if not asr_enabled():
        return AsrResult(text="", engine=None, error="ASR disabled (SCAMGRAPH_ASR=0)")

    media = Path(path)
    if not media.is_file():
        return AsrResult(text="", engine=None, error="file not found")

    try:
        size = media.stat().st_size
    except OSError as exc:
        return AsrResult(text="", engine=None, error=f"stat failed: {exc}"[:200])

    max_bytes = _max_bytes()
    if max_bytes and size > max_bytes:
        return AsrResult(
            text="",
            engine=None,
            error=f"file too large for ASR ({size} > {max_bytes} bytes)",
        )

    if not faster_whisper_available():
        return AsrResult(
            text="",
            engine=None,
            error="faster-whisper not installed (see requirements-optional.txt)",
        )

    audio_path: Path | None = None
    tmp_dir = None
    try:
        if media.suffix.lower() in _AUDIO_EXTS:
            audio_path = media
        else:
            if not ffmpeg_available():
                return AsrResult(text="", engine=None, error="ffmpeg not available for ASR")
            tmp_dir = tempfile.TemporaryDirectory(prefix="sg-asr-")
            audio_path = Path(tmp_dir.name) / "audio.wav"
            extracted = _extract_audio(media, audio_path)
            if extracted is not None:
                return AsrResult(text="", engine=None, error=extracted)

        return _run_whisper_timed(audio_path, language=language)
    finally:
        if tmp_dir is not None:
            tmp_dir.cleanup()


def _extract_audio(video: Path, dest: Path) -> str | None:
    """Extract mono 16 kHz wav. Returns error string or None on success."""
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(video),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        str(dest),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
    except Exception as exc:  # noqa: BLE001
        return f"ffmpeg audio extract failed: {exc}"[:200]
    if not dest.is_file() or dest.stat().st_size == 0:
        return "ffmpeg produced empty audio"
    return None


def _model_download_root() -> str | None:
    raw = os.environ.get("SCAMGRAPH_CACHE_DIR") or "data/cache"
    root = Path(raw) / "whisper"
    try:
        root.mkdir(parents=True, exist_ok=True)
        return str(root)
    except Exception:  # noqa: BLE001
        return None


def _run_whisper_timed(audio_path: Path, *, language: str | None) -> AsrResult:
    timeout = _timeout_s()
    with ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(_run_whisper, audio_path, language=language)
        try:
            return fut.result(timeout=timeout)
        except FuturesTimeout:
            return AsrResult(
                text="",
                engine="faster-whisper",
                error=f"ASR timeout after {timeout}s",
                model=_MODEL_SIZE,
            )


def _run_whisper(audio_path: Path, *, language: str | None) -> AsrResult:
    try:
        from faster_whisper import WhisperModel
    except Exception as exc:  # noqa: BLE001
        return AsrResult(
            text="",
            engine=None,
            error=f"faster-whisper import failed: {exc}"[:200],
        )

    download_root = _model_download_root()
    try:
        model = WhisperModel(
            _MODEL_SIZE,
            device="cpu",
            compute_type="int8",
            download_root=download_root,
            local_files_only=True,
        )
    except Exception as exc:  # noqa: BLE001
        return AsrResult(
            text="",
            engine="faster-whisper",
            error=f"model unavailable (offline/local): {exc}"[:200],
            model=_MODEL_SIZE,
        )

    try:
        segments, _info = model.transcribe(
            str(audio_path),
            language=language,
            vad_filter=True,
        )
        parts: list[str] = []
        for seg in segments:
            t = (getattr(seg, "text", None) or "").strip()
            if t:
                parts.append(t)
        text = " ".join(parts).strip()
        return AsrResult(
            text=text,
            engine="faster-whisper",
            model=_MODEL_SIZE,
            error=None if text else "empty transcript",
        )
    except Exception as exc:  # noqa: BLE001
        return AsrResult(
            text="",
            engine="faster-whisper",
            error=str(exc)[:200],
            model=_MODEL_SIZE,
        )
