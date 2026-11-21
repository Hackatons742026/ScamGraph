Configure `SCAMGRAPH_DB`, `SCAMGRAPH_DATA_DIR`, `SCAMGRAPH_CACHE_DIR`, `SCAMGRAPH_SALT`; run `uvicorn backend.api.main:app`.
Without DB, deterministic synthetic fixtures serve the API. `POST /api/import` queues configured data; poll `/api/runs/{id}`.
`GET /api/runs/latest`, `/incidents[/{id}]`, `/artifacts/{id}`, `/campaigns[/{id}]`, `/graph` read live projections;
graph accepts campaign/tier/level filters. `GET /api/media/{id}` serves files below configured data/cache roots.
`POST /api/classify` accepts multipart `files`, `text`, `url`, `exclude_incident`; request/file limits are 10/5 MB.
Filenames are reduced to basename; responses mask displays and omit hashes, source paths and OCR. Errors use `{error,detail}`.
