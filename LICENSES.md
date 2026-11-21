# Licences

Third-party components used by ScamGraph DNA. Keep this file honest: only list
what we actually ship or invoke. Final audit pass: task #17 (`codex-backend`).

## Python (runtime — `backend/requirements.txt`)

| Package | Use | Licence (upstream) |
|---|---|---|
| FastAPI | HTTP API | MIT |
| Uvicorn | ASGI server | BSD-3-Clause |
| Pydantic | Request/response models | MIT |
| httpx | API tests / TestClient stack | BSD-3-Clause |
| pytest | Tests | MIT |
| Pillow | Image load / OCR preprocess / frames | HPND (Pillow) |
| pytesseract | Tesseract Python wrapper | Apache-2.0 |
| ImageHash | Perceptual hash for near-duplicate frames/images | BSD-2-Clause / BSD-3-Clause (see upstream) |

## Optional Python (`backend/requirements-optional.txt` — not in CI)

| Package | Use | Licence (upstream) |
|---|---|---|
| EasyOCR | OCR fallback (`pl`) | Apache-2.0 |
| torch | EasyOCR dependency | BSD-style (PyTorch) |
| faster-whisper | Speech-to-text (nice-to-have #25) | MIT |

## System tools (ingest)

| Tool | Use | Licence |
|---|---|---|
| Tesseract OCR + `tesseract-ocr-pol` | Polish OCR default | Apache-2.0 |
| ffmpeg | Video key-frame extraction | LGPL/GPL (build-dependent; use a redistributable build) |

## Frontend

Frontend dependency licences are maintained under the frontend hand-over
(`docs/frontend.md` / #17 final pass).

## Data

NASK sample materials are **not** redistributed and must never appear in this
repository. See `.gitignore` (`data/`, artifact extensions outside fixtures).
