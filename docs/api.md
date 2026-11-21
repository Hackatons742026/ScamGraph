Set `SCAMGRAPH_DB`, `SCAMGRAPH_DATA_DIR`, `SCAMGRAPH_CACHE_DIR`, and `SCAMGRAPH_SALT`;
run `uvicorn backend.api.main:app`. Without a DB, deterministic demo fixtures are used.
- `POST /api/import`: queues the configured data root; poll its ID at `/api/runs/{id}`.
- `GET /api/runs/latest`, `/incidents`, `/incidents/{id}`, `/artifacts/{id}`: live summaries/details.
- `GET /api/campaigns`, `/campaigns/{id}`, `/graph`: persisted memory; graph accepts campaign/tier/level filters.
- `GET /api/media/{id}`: files only below configured data/cache roots.
- `POST /api/classify`: multipart `files`, `text`, `url`, `exclude_incident`; no DB mutation.
Classify limits are 10 MB/request and 5 MB/file; filenames are reduced to basename.
Responses expose masked display fields, never hashes/source paths/OCR. Errors are `{error,detail}`;
runs move pending → running → done/failed and preserve a sanitized failure message.
