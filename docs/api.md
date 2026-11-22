# API reference

Run `uvicorn backend.api.main:app --host 127.0.0.1 --port 8000` from the
repository root. Set `SCAMGRAPH_DB` to enable live reads; set
`SCAMGRAPH_DATA_DIR` as well for batch imports. `SCAMGRAPH_SALT` is required by
pipeline operations and `SCAMGRAPH_CACHE_DIR` controls generated media. Live
Classify uploads require `SCAMGRAPH_DB`, `SCAMGRAPH_SALT`, and a writable cache,
but do not require a source dataset directory. Without
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
| `POST /api/classify` | Analyze a multipart upload, text, or URL against stored memory; live submissions are saved for future comparison |
| `GET /api/eval/report` | Deterministic synthetic scenarios and report contract |
| `POST /api/edges/{edge_id}/decision` | Record an analyst's confirm/reject decision for a stored edge |
| `POST /api/campaigns/merge` | Merge two or more campaign groups, preserving their incident membership |
| `POST /api/campaigns/split` | Move a proper subset of campaign members into a new campaign |

`POST /api/classify` accepts multipart fields `files`, `text`, `url`, and
`exclude_incident`. Each uploaded file may be up to 50 MB and the whole request
up to 100 MB (real HAR captures and videos are often larger than 5 MB); set
`SCAMGRAPH_MAX_UPLOAD_FILE_MB` and `SCAMGRAPH_MAX_UPLOAD_REQUEST_MB` to change
the limits. Filenames are reduced to basenames. Public projections mask
display values and omit evidence hashes and filesystem paths: saved-page assets
are shown as `local:<file name>` and compared by content. OCR text is returned
only with artifact-detail media when available. Errors use
`{ "error": "…", "detail": "…" }`. Override routes require a configured live
database. They persist changes and audit records; rejecting an edge removes it
from graph and incident projections and re-runs the grouping, so the link stops
holding incidents together immediately. In synthetic mode they return HTTP 501.
Campaign merge/split accepts an optional note; notes are capped at 500
characters and stored only in the local audit log.

Live graph, incident, and campaign edge projections include `analyst_override`
for the latest Confirm/Reject audit record (`decision`, `recorded_at`, and
optional `note`). This lets clients restore the displayed decision after a
refresh. Rejected edges remain omitted from those projections; their action and
note remain in the SQLite audit history.

In live mode, a normal classify request is stored as a new incident with its
parsed artifacts, evidence, and media in the app-managed cache and database.
The API rebuilds links, campaigns, and decisions before returning, so later
classify requests compare against earlier uploads and the new incident appears
in live views. Supplying `exclude_incident` runs leave-one-out analysis and does
not save another incident, and its candidate links never include the excluded
incident. A saved classify response reports the stored decision, so Classify and
the incident list always agree. Files that could not be fully parsed are listed
as extra `coverage` reasons with a safe, actionable message.

Live projections derived from stored captures:

- `IncidentDetail.funnel` comes from `strona_N` steps, or from artifact roles
  (ad → prelander → offer → order) when there are none. Each step names its
  first-party page domain and lists only first-party redirect hops; ad-tech
  pixels are left out.
- `ArtifactDetail` returns HAR pages, the full redirect chain, the request count,
  the busiest hosts, and media pixel sizes.
- `GET /api/campaigns/{id}/links` lists other groups connected by a
  non-rejected edge, with their shared evidence.
- Stored decisions agree with membership: an incident in a campaign has
  outcome `known_campaign` with a "Grouped with N other incidents" reason.
  Other incidents keep their leave-one-out decision.
- Campaign and network numbers are stored once and never reused, so labels do
  not shift after a merge or split.
- Coverage badges name the gaps that weaken a decision (`no HAR`, `video only`,
  `media only`); `level` is `low` only when one applies. A capture bundle counts
  as having a HAR.
- `RunSummary.artifacts_by_kind[*].partial` counts artifacts parsed with gaps
  (included in `parsed`).
- Evidence on large shared platforms (Google, Facebook, app stores, …) is kept
  for explanation with `ignore_reason: "platform_domain"` and never creates an
  edge.

Without a live database, classify returns a
deterministic demo response and does not store the submitted material.

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
