# Data model

Shared between ingestion (`cursor-backend`) and persistence/API (`codex-backend`).
Source of truth for tables: `backend/db/schema.sql`. Source of truth for pipeline
dataclasses: `backend/pipeline/models.py` (changes require an `api_change`).

## Pipeline dataclasses

| Type | Role |
|---|---|
| `Incident` | One top-level case folder; carries `coverage` and artifact list |
| `Artifact` | One discovered file/bundle (`kind`, `path`, `funnel_step`, `role`, `parse_status`) |
| `Evidence` | Typed observation: `type`, `tier` (A/B/C), `family`, `value_hash`, `display`, `ignored`, `ignore_reason`, `artifact_id`, `funnel_step` |
| `Coverage` | Per-incident `kinds_present` / `kinds_missing` / `artifact_counts` / `notes` |
| `MediaRef` | Screenshot or video frame under `$SCAMGRAPH_CACHE_DIR` (`path` relative, e.g. `media/<sha256>.jpg`) |
| `IncidentBundle` | In-memory classify result from `process_input` (no DB writes) |

`ArtifactKind`: `har`, `html`, `mhtml`, `bundle`, `image`, `video`, `adlib_json`, `text`, `url`, `unknown`.

## SQLite tables (ingest writes)

Ingestion persists **only** through `backend.db.Repository` — never raw SQL.

| Table | Written by ingest? | Notes |
|---|---|---|
| `runs` | yes | Import job summary (`save_run`) |
| `incidents` | yes | `coverage_json` from `Coverage.to_dict()` |
| `artifacts` | yes | `parse_status` ∈ ok/partial/failed |
| `evidence` | yes | Only `display_value` / hashes — never raw secrets |
| `media` | yes | `path` relative to `SCAMGRAPH_CACHE_DIR` |
| `pages` / `requests` | no (reserved) | Optional finer HAR/page rows for later |
| `edges` / `campaigns` / `membership` / `decisions` | yes | Live import rebuilds derived engine state and persists leave-one-out decisions |
| `audit_log` | no | API / overrides |

## Evidence conventions

- Equality uses `value_hash` (`sha256(SALT+value)[:12]` for secrets and many IDs).
- `ignored=true` rows stay in the DB so the UI can show `ignore_reason`
  (`cdn_ip`, `public_lib`, `placeholder_phone`, `small_doc`, …).
- Tier-B `family` ∈ `kit` | `tds` | `domain` | `creative` | `hosting`; tier A/C use `family=null`.

## Confidentiality

`data/` (raw dataset, SQLite, cache) is git-ignored. Never commit dataset files or
raw tokens/PII. See `docs/ingestion.md`.
