# Live API

Set `SCAMGRAPH_DB`, `SCAMGRAPH_DATA_DIR`, `SCAMGRAPH_CACHE_DIR`, and
`SCAMGRAPH_SALT`, then run `uvicorn backend.api.main:app`. Without a database
setting the contract endpoints use deterministic synthetic demo fixtures.

`POST /api/import` queues ingestion from `SCAMGRAPH_DATA_DIR`; poll the returned
run through `/api/runs/{id}` or `/api/runs/latest`. Ingestion persists masked
evidence, builds links and campaign memory, and records failures on the run.
Read endpoints project SQLite rows to contract v1 and never return hashes or
source paths. `/api/media/{id}` serves only files located below the configured
data/cache roots.

`POST /api/classify` accepts multipart `files`, `text`, `url`, and optional
`exclude_incident`. The request limit is 10 MB, each file is limited to 5 MB,
and uploaded filenames are reduced to their basename. Classification is
in-memory and does not mutate the repository. Errors always use
`{"error": "…", "detail": "…"}`.
