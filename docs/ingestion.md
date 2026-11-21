# Ingestion pipeline

Owned by **cursor-backend** (`backend/pipeline/**`).

## What it does

1. **Discover** incident folders and artifact kinds (HAR, HTML/`*_files`, MHTML, capture bundle, image, video, Ad Library `*.info.json`, funnel `strona_N`).
2. **Parse** each artifact in isolation (`ok` / `partial` / `failed`).
3. **Redact** secrets before anything is retained (`SCAMGRAPH_SALT` required).
4. **Dedup** exact duplicates (observation counts) and link variants.
5. **Extract** tiered evidence (A/B/C + family) with `ignore_reason` kept for explanations.
6. **Persist** via `backend.db.Repository` only (no raw SQL in the pipeline).

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
| `SCAMGRAPH_CACHE_DIR` | no | `data/cache` | Frames / screenshots (`media/<sha256>.*`) |

System tools: `ffmpeg` (video frames), `tesseract` + `tesseract-ocr-pol` (OCR). Missing tools soft-fail (`PARTIAL` / empty OCR).

Optional heavy deps: `backend/requirements-optional.txt` (EasyOCR, faster-whisper).

## Safety

- Never commit `data/` or raw HAR/MHTML/MP4/dataset files.
- Fixtures are synthetic builders under `backend/tests/fixtures/**`.
- No hard-coded incident IDs. No network calls in the core pipeline.
