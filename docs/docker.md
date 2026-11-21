# Docker development and test workflow

Docker Compose packages the production frontend build with FastAPI. The default
stack seeds a small synthetic live database, serves the UI and API from one
origin, and keeps database/cache state in a named Docker volume.

## Start the synthetic demo

```bash
docker compose up --build -d
```

Open <http://localhost:8000>. The same-origin API is available under `/api`,
and `/api/health` is the container health check. `SCAMGRAPH_PORT` changes the
host port; for example `SCAMGRAPH_PORT=8080 docker compose up --build -d`.

The demo database persists in the `scamgraph-state` volume. Stop the services
and remove that synthetic database with:

```bash
docker compose down -v
```

The Compose default salt (`synthetic-docker-demo-salt`) is only for synthetic
testing. Set a stable private `SCAMGRAPH_SALT` when using a separate live-data
setup; do not use the demo default for real captures.

## Run the checks in containers

Each command builds its target if needed:

```bash
docker compose --profile test run --rm backend-tests
docker compose --profile test run --rm frontend-tests
docker compose --profile test run --rm live-smoke
```

`backend-tests` runs `pytest backend/tests -q`. `frontend-tests` runs ESLint,
Vitest, and the production TypeScript/Vite build. `live-smoke` waits for the app
health check, verifies the frontend/API same-origin shell, and checks the live
API response shapes against `frontend/openapi.snapshot.json`.

## Build and data boundaries

`Dockerfile` uses a Node build stage for the frontend and a Python runtime stage
for FastAPI. The runtime serves the generated `frontend/dist` assets and needs
no Node process. Compose uses a local synthetic-only seed container to prepare
the demo DB before the app starts.

`.dockerignore` excludes local `.env` files, databases, caches, `data/`, raw
capture formats, local virtual environments, `node_modules`, and prebuilt
frontend assets. Source captures and secrets are never copied into the image.
The app volume stores only its DB/cache state. The default demo does not mount
the host `data/` directory and leaves import disabled until an input directory
is explicitly mounted and configured.

For a controlled data import, create a separate Compose override that mounts the
approved input directory read-only at `/data`, sets `SCAMGRAPH_DATA_DIR=/data`,
sets `SCAMGRAPH_DB` to a path in the state volume, and supplies a private stable
`SCAMGRAPH_SALT`. Do not add the input directory, override containing secrets,
or database to the repository or Docker image. Keep the synthetic demo volume
separate from any live-data environment.
