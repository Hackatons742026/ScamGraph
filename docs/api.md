# Live API
Set `SCAMGRAPH_DB`, `SCAMGRAPH_DATA_DIR`, `SCAMGRAPH_CACHE_DIR`, and
`SCAMGRAPH_SALT`; run `uvicorn backend.api.main:app`. Without a DB, endpoints
use deterministic demo fixtures.
`POST /api/import` queues ingestion from the configured data root; poll its ID
through `/api/runs/{id}`. It persists masked evidence, links and campaign memory.
Reads never return hashes or source paths; media is restricted to data/cache roots.
`POST /api/classify` accepts multipart `files`, `text`, `url`, and
`exclude_incident`; limits are 10 MB/request and 5 MB/file, filenames use basename,
and classification is in-memory. Errors use `{"error":"…","detail":"…"}`.
