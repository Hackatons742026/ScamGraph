# Frontend — ScamGraph DNA

React 18 + TypeScript (strict) + Vite 8 + Tailwind 4 single-page app. It shows incidents, evidence,
campaigns and networks, and explains every decision. Owner: `claude-frontend`. Code: `frontend/`.

## Run

```bash
cd frontend
npm ci
VITE_USE_MOCKS=true npm run dev   # synthetic data, no backend needed → http://localhost:5173
npm run dev                       # live: proxies /api → http://localhost:8000 (backend must run)
```

| Command | What it does |
|---|---|
| `npm run lint` | ESLint (TS, React hooks, fast refresh) |
| `npm run test -- --run` | Vitest + Testing Library, once |
| `npm run build` | `tsc -b` type check + production build to `frontend/dist` (served by FastAPI for the demo) |
| `npm run gen:api` | Regenerate `src/api/schema.d.ts` from `openapi.snapshot.json` |
| `npm run gen:api:live` | Fetch the running backend's `/openapi.json` into `openapi.snapshot.json`, then regenerate |
| `npm run smoke:live` | Check every screen's GET endpoint on a running backend against the snapshot (see Live mode) |

## Mock mode (demo fallback)

`VITE_USE_MOCKS=true` swaps the HTTP transport of the API client for `src/mocks/handlers.ts`. That
transport answers **every** contract-v1 endpoint from `src/mocks/data.ts`. The fixtures are synthetic
only: domains end in `.test`, IPs are TEST-NET, and IDs are invented. A yellow banner is always shown in
mock mode, so screenshots can't be mistaken for real results. Mock mode must keep working until the end
of the hackathon.

The fixtures are typed TypeScript instead of JSON, so `tsc` fails as soon as they drift from the contract.

## API types

- Source of truth: `/generated/api-contract.md` (owner `codex-backend`).
- `openapi.snapshot.json` is the backend's exported `/openapi.json`. It's committed so builds and CI don't need a running backend.
  After a backend API change, run `npm run gen:api:live` and commit both the snapshot and `schema.d.ts`.
- Path parameters use the backend's names (`{incident_id}`, `{run_id}`, …). The URLs match the contract.
- Never hand-write a contract type. Import aliases from `src/api/types.ts`; they are generated types.
- Errors use `{error, detail}`. `unwrap()` turns them into `ApiRequestError`, and `QueryState` renders them.

## Live mode

Without `VITE_USE_MOCKS`, the app calls the real API. FastAPI serves the production build same-origin:

```bash
cd frontend && npm run build && cd ..
SCAMGRAPH_DB=/path/outside/repo/scamgraph.db uvicorn backend.api.main:app --port 8000   # → http://localhost:8000
cd frontend && npm run smoke:live
```

`smoke:live` validates each endpoint against `openapi.snapshot.json` and fails if the snapshot no longer equals
the live `/openapi.json`. It also checks that the built app is served on `/graph`. It prints warnings for data that
would make a demo hard to read (identical labels, links without evidence…). It never prints values.

To try live mode without the dataset, create a synthetic database. The backend's own engine links and clusters it:

```bash
SCAMGRAPH_SALT=synthetic-dev-salt python frontend/scripts/seed-synthetic-live-db.py /tmp/scamgraph-synthetic.db
```

## Structure

```
src/api/          client.ts (openapi-fetch + unwrap + mediaUrl), types.ts (aliases), schema.d.ts (generated)
src/mocks/        data.ts (synthetic fixtures), handlers.ts (mock transport)
src/components/   ui/ (shadcn-style primitives), domain/ (TierBadge, FamilyLabel, CoverageBadges,
                  OutcomeBadge, QueryState), layout/ (AppShell, PageHeader)
src/lib/          domain.ts (all user-facing labels + tier/family colours), env.ts, utils.ts
src/pages/        one component per route (routes in src/routes.tsx)
```

## UI rules

- Every screen uses `QueryState`, which handles the loading, error (with retry) and empty states.
- Evidence always shows a tier badge (A/B/C), its family, the masked `display` value, and the source artifact and funnel step.
- Never render raw identifiers. Only render `display` / `*_display` fields from the API.
- Tier and family colours live in `src/lib/domain.ts`. The graph uses the same values.
- No incident IDs or expected results are hard-coded in UI code.

## Testing notes

- Component tests run in jsdom (`src/test/render.tsx` renders the full app at a route).
- Tests that send multipart bodies run in the Node environment (`// @vitest-environment node`).
  jsdom's `File`/`FormData` can't be serialised by Node's native `Request`.
