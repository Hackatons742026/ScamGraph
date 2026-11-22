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

## Manually upload ads

Use the separate `compose.live.yaml` stack to analyze ads you upload through
the Classify page. No host dataset directory is mounted or read. Each normal
Classify submission is stored as a new incident in the live database and used
as memory when analyzing later uploads. Uploaded files live in the app-managed
cache; the analysis database and cache use a dedicated volume scoped by a
required project name. Use the same name for this collection on later runs and
a different name for another collection. The live stack does not seed or reuse
the synthetic demo database and exposes port `8001` only on this computer.

From the repository root, set a stable collection name and salt:

```bash
export SCAMGRAPH_LIVE_PROJECT_NAME=scamgraph-manual-uploads
openssl rand -hex 32
# Save this value privately; set the same value in the next line and on future runs.
export SCAMGRAPH_SALT='paste-the-generated-private-value-here'
docker compose -f compose.live.yaml up --build -d
```

Keep the same salt and project name for future runs to reuse the collection.
Choose a different project name when you intentionally want an empty separate
collection. Do not commit the salt or generated database/cache files. In a new
terminal, export the same two variables again before running any Compose
command, including `ps` or `down`.

Open <http://localhost:8001>, select **Classify**, upload one ad (HAR, saved
page, image, video, or supported JSON), and click **Classify**. A normal
submission adds the ad to the collection for later comparison. Leave-one-out
classification is analysis-only and is not saved. The **Run import** action is
for a mounted batch directory; individual uploaded ads do not need it.

Confirm the container is healthy with:

```bash
docker compose -f compose.live.yaml ps
```

To stop the live stack and keep its database for the next session:

```bash
docker compose -f compose.live.yaml down
```

Do not use `down -v` unless you intend to erase the saved uploads, analysis
database, and cache for this project name.
