# API reference

Run `uvicorn backend.api.main:app --host 127.0.0.1 --port 8000` from the
repository root. Set `SCAMGRAPH_DB` to enable live reads; set
`SCAMGRAPH_DATA_DIR` as well to import data. `SCAMGRAPH_SALT` is required by
pipeline operations and `SCAMGRAPH_CACHE_DIR` controls generated media. Without
`SCAMGRAPH_DB`, read endpoints return deterministic synthetic demo fixtures;
`POST /api/import` in this mode returns the demo run and does not import files.

## Endpoints

| Method and path | Behavior |
|---|---|
| `GET /api/health` | Service status and API version |
| `POST /api/import` | Queue a live import; returns HTTP 202 and a run ID |
| `GET /api/runs/{id}` / `GET /api/runs/latest` | Import status and summary |
| `GET /api/incidents` / `GET /api/incidents/{id}` | Incident summaries or details; list supports `status` and `campaign` filters |
| `GET /api/artifacts/{id}` | Artifact metadata and media references |
| `GET /api/media/{id}` | Serve media only from configured data/cache roots |
| `GET /api/campaigns` / `GET /api/campaigns/{id}` | Campaign summaries or details |
| `GET /api/campaigns/{id}/links` | Campaign link projection |
| `GET /api/graph` | Graph nodes and edges; optional `campaign`, comma-separated `tiers`, and `levels` filters |
| `POST /api/classify` | Classify a multipart upload, text, or URL against stored memory |
| `GET /api/eval/report` | Deterministic synthetic scenarios and report contract |

`POST /api/classify` accepts multipart fields `files`, `text`, `url`, and
`exclude_incident`. The whole request limit is 10 MB and each uploaded file is
limited to 5 MB. Filenames are reduced to basenames. Public projections mask
display values and omit evidence hashes, source paths, and OCR text. Errors use
`{ "error": "…", "detail": "…" }`. Optional mutation and export routes may
be present in OpenAPI but currently return HTTP 501.

The full response schemas are defined in `backend/api/schemas.py`; inspect
`/openapi.json` on a running service for the generated OpenAPI document.
