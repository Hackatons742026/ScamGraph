# ScamGraph DNA v2.4 — Final Docker Regression Report

**Run date:** 2026-11-22  
**Branch:** `room/48-docker-reliability-final`  
**Test project:** `sg-final-regression-20261122-r1` (synthetic data only)

## Results

| Check | Result | Evidence |
|---|---|---|
| Fresh Live volume permissions | **PASS** | New `scamgraph-live-state` volume inherited owner `10001:999`, mode `0750`; API process reported UID/GID `10001:999`. |
| SQLite initialization and readiness | **PASS** | `/api/health` initialized the isolated database; `PRAGMA quick_check` returned `ok` and 12 tables were present. Unusable DB path returns a safe HTTP 503; covered by `backend/tests/api/test_health.py`. |
| Persistence through restart/rebuild | **PASS** | A synthetic text upload remained available after app restart and image recreation using the same isolated volume. |
| Docker health and logs | **PASS** | Final container was `healthy`, restart count `0`; scan of its recent logs found no `OperationalError`, `PermissionError`, traceback, `ERROR`, or exception lines. |
| Backend suite in final Docker image | **PASS** | `135 passed, 1 skipped`; run network-disabled with no database volume mounted. One Starlette/httpx deprecation warning. |
| Frontend lint | **PASS** | `npm run lint` completed with no findings. |
| Frontend tests | **PASS** | Vitest: 26 files, 191 tests passed. |
| TypeScript and production build | **PASS** | `npm run build` completed (`tsc -b` and Vite production build). Vite reports the existing main bundle is over 500 kB. |
| OpenAPI and endpoint compatibility | **PASS** | Final `npm run smoke:live` matched every checked endpoint and the live OpenAPI document to the committed snapshot. The snapshot and generated types were synchronized from the isolated app. |
| Seven synthetic validation scenarios | **PASS** | API evaluation report returned 7/7 passing: Exact tier-A match, Multi-signal match, Network-only link, No shared evidence, Insufficient coverage, Conflicting campaigns, Excluded incident. |
| Tier A, Campaign Memory, graph consistency | **PASS** | Full backend suite includes Tier A linking/provenance, memory classification, live campaign/graph projection, and upload reanalysis tests. No thresholds or scoring rules changed. |
| Confirm, Reject, Split, Merge and audit | **PASS** | Full backend suite verifies persisted decisions, latest decision, rejected-link behavior across merge/recompute, and audit events for all four actions. |
| OCR and image parsing | **PASS** | Runtime Tesseract listed `eng`, `osd`, `pol`; synthetic Polish text used Tesseract with no language fallback error. PNG/JPEG/WEBP parsing retained SHA-256 and pHash. Malformed image now fails with a safe message and no media record. |
| Exact duplicate and visual variant handling | **PASS** | Full backend suite verifies identical WEBP uploads remain separate observations with an exact-duplicate indicator; visual variants retain distinct hashes and pHash without forced campaign linking. |
| HTML, CSV and MISP exports | **PASS** | Full backend suite covers export shapes, redaction/escaping, source-date behavior, and CSV formula-injection neutralization. |

## Skipped and notes

- **SKIPPED:** `backend/tests/pipeline/test_media_adlib_funnel.py` video keyframe test because `ffmpeg` is not installed in the runtime image. Video extraction was not verified in Docker.
- **Resolved during this run:** the first live OpenAPI smoke found snapshot drift (including missing `IncidentDetail.ingested_at` and response-schema differences). Snapshot and TypeScript declarations were regenerated from the isolated app; the final smoke passed.
- The fresh isolated database had no import run, so `/api/runs/latest` returned 404 and the smoke emitted its expected “no import run yet” warning.
- Existing Live databases and volumes were not inspected for contents or modified. Test volumes were retained; no volume deletion/reset command was run. No push or merge was performed.

## Changes

- Docker image now prepares both state mountpoints for UID/GID `10001:999` with private `0750` permissions before Docker mounts a fresh named volume. FastAPI remains non-root.
- Docker image now includes Tesseract with offline English and Polish language data.
- `/api/health` now initializes and checks configured SQLite readiness using `PRAGMA quick_check`, returning a safe 503 when unavailable.
- Image parsing validates decodability before caching; regression coverage exercises PNG, JPEG, WEBP, and malformed files.
- OpenAPI snapshot and generated TypeScript declarations now match the Docker runtime schema.
