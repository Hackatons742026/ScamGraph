# ScamGraph DNA

ScamGraph is an offline analysis tool that compares suspicious advertising artifacts and groups explainable links into probable campaigns. It reports evidence and coverage; it does not make a legal finding or identify people.

## Quick start

Use Python 3.11 and a virtual environment. On macOS/Linux, from the repository root:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
export SCAMGRAPH_SALT='private-machine-specific-value'
export SCAMGRAPH_DATA_DIR='/absolute/path/to/private/input'
export SCAMGRAPH_DB='/absolute/path/to/private/scamgraph.db'
export SCAMGRAPH_CACHE_DIR='/absolute/path/to/private/cache'
python -m backend.pipeline.run --data "$SCAMGRAPH_DATA_DIR" --db "$SCAMGRAPH_DB"
cd frontend && npm ci && npm run build && cd ..
uvicorn backend.api.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. The CLI command performs an import; the API also accepts `POST /api/import` when `SCAMGRAPH_DB` and `SCAMGRAPH_DATA_DIR` are configured, and the returned run ID can be polled at `/api/runs/{id}`. If `SCAMGRAPH_DB` is unset, API reads use deterministic synthetic demo fixtures and import does not process local data. Set a stable, private salt for repeated runs; changing it changes salted identifiers. See [API reference](docs/api.md) and [ingestion runbook](docs/ingestion.md).

For video frame extraction install `ffmpeg`; OCR uses `tesseract` and its Polish language data. Missing system tools soft-fail and reduce coverage. Optional neural OCR/speech packages are listed in `backend/requirements-optional.txt` and are not required for the core pipeline. Check [LICENSES.md](LICENSES.md) before redistributing binaries, packages, or model weights.

## Development checks

```bash
python -m pip install -r backend/requirements.txt
SCAMGRAPH_SALT=synthetic-test-salt python -m pytest backend/tests -q
cd frontend && npm ci && npm run lint && npm run test -- --run && npm run build
```

The backend suite uses synthetic fixtures. CI also installs `ffmpeg` and Tesseract so media checks can run; media tests skip when those tools are absent.

## Data handling

- Keep raw captures, local databases, caches, labels, and machine-specific salts outside version control. `data/` is ignored; never add source captures or outputs to a commit.
- Set a stable private `SCAMGRAPH_SALT` for each controlled environment. Changing it changes salted identifiers and prevents matching old hashes.
- Public API projections mask display values and omit raw hashes, source paths, and OCR text. Restrict the service to trusted local users; protect uploads, database files, and backups using the organization’s access controls.
- Test data must be synthetic. Do not put real domains, identifiers, account data, URLs, or screenshots in fixtures, logs, issues, or documentation.

## Design and evaluation

Read [methodology](docs/methodology.md), [data model](docs/data_model.md), [similarity rules](docs/similarity.md), [clustering and memory](docs/clustering.md), and [evaluation](docs/scenarios.md). Evaluation labels are supplied from an explicit local CSV and are never committed.
