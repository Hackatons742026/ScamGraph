Set `SCAMGRAPH_DB`, `SCAMGRAPH_DATA_DIR`, `SCAMGRAPH_CACHE_DIR`, `SCAMGRAPH_SALT`; run `uvicorn backend.api.main:app`.
`POST /api/import` uses only the configured root; reads hide hashes/paths and media stays below safe roots.
Multipart classify is in-memory (10 MB/request, 5 MB/file, basename filenames); errors use `{error,detail}`.
