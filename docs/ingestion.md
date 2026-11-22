# Ingestion pipeline

Owned by **cursor-backend** (`backend/pipeline/**`).

## What it does

1. **Discover** incident folders and artifact kinds (HAR, HTML/`*_files`, MHTML, capture bundle — also when nested up to four folders deep — image, video, Ad Library `*.info.json` or any small `.json` whose content is an Ad Library record, funnel `strona_N`).
2. **Parse** each artifact in isolation (`ok` / `partial` / `failed`).
3. **Redact** secrets before anything is retained (`SCAMGRAPH_SALT` required).
4. **Dedup** exact duplicates (observation counts) and link variants.
5. **Extract** tiered evidence (A/B/C + family) with `ignore_reason` kept for explanations.
6. **Persist** via `backend.db.Repository` only (no raw SQL in the pipeline):
   artifacts, evidence, media, and the redacted HAR requests, redirect hops and
   pages behind the funnel and artifact-detail views. A re-import replaces an
   incident's evidence and drops artifacts that are no longer on disk.

Capture times come from HAR `startedDateTime`, capture-bundle manifests and Ad
Library `timestamp` / `upload_date` / `epoch`; an incident's first and last seen
dates are the earliest and latest of them. Pasted text and submitted URLs yield
contact, sentence and domain evidence. Relative links, file names and other
single-label hosts never become domain evidence, and local file paths never
reach evidence displays. The Docker image ships `ffmpeg`, so video frames and
their OCR are part of the containerized pipeline.

## Commands

```bash
set SCAMGRAPH_SALT=your-machine-salt
set SCAMGRAPH_DATA_DIR=data/raw
set SCAMGRAPH_DB=data/scamgraph.db
set SCAMGRAPH_CACHE_DIR=data/cache

pip install -r backend/requirements.txt
python -m backend.pipeline.run --data %SCAMGRAPH_DATA_DIR% --db %SCAMGRAPH_DB%
```

`--no-persist` runs parse/extract without writing the database.

## Classify entrypoint (no DB)

```python
from pathlib import Path
from backend.pipeline.run import process_input

bundle = process_input(
    paths=[Path("upload/")],
    text="optional pasted text",
    url="https://example-scam.test/landing",
)
# bundle.incident / artifacts / evidence / coverage / media
```

Used by `POST /api/classify` (co-5).

## Environment

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `SCAMGRAPH_SALT` | yes | — | Salted hashes for secrets / IDs |
| `SCAMGRAPH_DATA_DIR` | for CLI | `data/raw` | Dataset root |
| `SCAMGRAPH_DB` | for persist | `data/scamgraph.db` | SQLite path |
| `SCAMGRAPH_CACHE_DIR` | no | `data/cache` | Frames / screenshots (`media/<sha256>.*`); whisper cache under `whisper/` |
| `SCAMGRAPH_ASR` | no | `1` | Set `0` to disable optional speech-to-text |
| `SCAMGRAPH_ASR_TIMEOUT` | no | `120` | Soft timeout (seconds) for whisper inference |
| `SCAMGRAPH_ASR_MAX_BYTES` | no | `52428800` | Skip ASR when media exceeds this size |

System tools: `ffmpeg` (video frames + ASR audio extract), `tesseract` + the
`tesseract-ocr-pol` and `tesseract-ocr-eng` trained data (OCR). The Docker image
installs and verifies Polish Tesseract data at build time, so OCR works offline
at runtime without downloading models. Missing optional tools soft-fail; a
valid image remains available as `PARTIAL` with its cached media and pHash.
Malformed images fail with a safe format hint. Optional EasyOCR is not part of
the default offline image because its model weights require separate local
provisioning.

Optional heavy deps: `backend/requirements-optional.txt` (EasyOCR, faster-whisper). ASR uses faster-whisper **small**, offline (`local_files_only`); missing package/model never fails the run — empty transcript, no crash. Transcript sentences (≥10 words, same gate as OCR/HTML extractors) become tier-C `shared_sentence` evidence.

## Safety

- Never commit `data/` or raw HAR/MHTML/MP4/dataset files.
- Fixtures are synthetic builders under `backend/tests/fixtures/**`.
- No hard-coded incident IDs. No network calls in the core pipeline.
