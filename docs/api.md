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
| `POST /api/edges/{edge_id}/decision` | Record an analyst's confirm/reject decision for a stored edge |
| `POST /api/campaigns/merge` | Merge two or more campaign groups, preserving their incident membership |
| `POST /api/campaigns/split` | Move a proper subset of campaign members into a new campaign |

`POST /api/classify` accepts multipart fields `files`, `text`, `url`, and
`exclude_incident`. The whole request limit is 10 MB and each uploaded file is
limited to 5 MB. Filenames are reduced to basenames. Public projections mask
display values and omit evidence hashes, source paths, and OCR text. Errors use
`{ "error": "…", "detail": "…" }`. Override routes require a configured live
database. They persist changes and audit records; rejecting an edge removes it
from graph and incident projections. In synthetic mode they return HTTP 501.
Campaign merge/split accepts an optional note; notes are capped at 500
characters and stored only in the local audit log.

## Campaign exports

Exports require live mode (`SCAMGRAPH_DB`) and a valid campaign-level ID. Each
response is an attachment with `Cache-Control: no-store` and
`X-Content-Type-Options: nosniff`:

| Method and path | Content type |
|---|---|
| `GET /api/exports/{campaign}.html` | `text/html; charset=utf-8` |
| `GET /api/exports/{campaign}.csv` | `text/csv; charset=utf-8` |
| `GET /api/exports/{campaign}.misp.json` | `application/json` (MISP core event envelope) |

The self-contained HTML contains campaign members, artifact provenance,
evidence tiers/families, and campaign links. CSV contains separate rows for
incidents, artifacts, evidence observations, and campaign edges. MISP JSON
contains masked text attributes with `to_ids: false`; it is a reporting artifact,
not an indicator feed for automated blocking. All formats use keyed pseudonymous
references for campaigns, incidents, artifacts, and values. They omit raw
display values, evidence hashes, filesystem paths, filenames, capture content,
and OCR. The export key is `SCAMGRAPH_SALT`, so exports are stable only while
that private salt remains unchanged. Unknown campaigns, network IDs, and
unsupported suffixes return 404; exports without a configured live database
return 501. The JSON envelope follows the [official MISP core format](https://github.com/MISP/misp-rfc/blob/main/misp-core-format/raw.md).

The full response schemas are defined in `backend/api/schemas.py`; inspect
`/openapi.json` on a running service for the generated OpenAPI document.
