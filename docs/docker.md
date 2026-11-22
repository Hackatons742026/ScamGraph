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

## Import a local dataset

Use the separate `compose.live.yaml` stack for real local data. It mounts the
input directory read-only at `/data`, sets `SCAMGRAPH_DATA_DIR=/data`, requires
a stable private salt, and writes results to a dedicated `scamgraph-live-state`
volume scoped by a required live project name. Use the same name for this
dataset on later runs and a different name for another dataset. It does not
seed or reuse the synthetic demo database. The live UI uses port `8001` by
default; the synthetic demo can remain on `8000`.

Set `SCAMGRAPH_DATA_HOST_PATH` to the dataset folder's absolute path. If
`do_udostepnienia` is directly inside the project, run this from the repository
root; otherwise replace the path with the folder's actual location:

```bash
export SCAMGRAPH_DATA_HOST_PATH="$PWD/do_udostepnienia"
export SCAMGRAPH_LIVE_PROJECT_NAME=scamgraph-live-do-udostepnienia
if [ ! -d "$SCAMGRAPH_DATA_HOST_PATH" ]; then
  echo "Dataset directory not found: $SCAMGRAPH_DATA_HOST_PATH"
fi
openssl rand -hex 32
# Save this value privately; set the same value in the next line and on future runs.
export SCAMGRAPH_SALT='paste-the-generated-private-value-here'
if [ -d "$SCAMGRAPH_DATA_HOST_PATH" ]; then
  docker compose -f compose.live.yaml up --build -d
fi
```

The app exposes port `8001` only on this computer. Keep the same salt for future
runs against this dataset and keep `SCAMGRAPH_LIVE_PROJECT_NAME` stable to reuse
its database. Do not commit the salt, the dataset, or generated database files.
The input mount is read-only; the app stores only its analysis database and
cache in the separate named volume. On macOS, Docker Desktop must be allowed to
share the selected folder, and its files must be readable. In a new terminal,
export the same three variables again before running any Compose command,
including `ps` or `down`.

Open <http://localhost:8001>, go to **Overview**, then click **Run import**.
The UI polls the run status and refreshes the live views when processing
finishes. Confirm the container is healthy with:

```bash
docker compose -f compose.live.yaml ps
```

To stop the live stack and keep its database for the next session:

```bash
docker compose -f compose.live.yaml down
```

Do not use `down -v` unless you intend to erase the live analysis database.
