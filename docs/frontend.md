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
| `npm run gen:api` | Regenerate `src/api/schema.d.ts` from `openapi.snapshot.yaml` |
| `npm run gen:api:live` | Regenerate from the running backend's `http://localhost:8000/openapi.json` |

## Mock mode (demo fallback)

`VITE_USE_MOCKS=true` swaps the HTTP transport of the API client for `src/mocks/handlers.ts`. That
transport answers **every** contract-v1 endpoint from `src/mocks/data.ts`. The fixtures are synthetic
only: domains end in `.test`, IPs are TEST-NET, and IDs are invented. A yellow banner is always shown in
mock mode, so screenshots can't be mistaken for real results. Mock mode must keep working until the end
of the hackathon.

The fixtures are typed TypeScript instead of JSON, so `tsc` fails as soon as they drift from the contract.

## API types

- Source of truth: `/generated/api-contract.md` (owner `codex-backend`).
- `openapi.snapshot.yaml` mirrors contract v1 until the backend serves `/openapi.json`. After that, use `npm run gen:api:live`.
- Never hand-write a contract type. Import aliases from `src/api/types.ts`; they are generated types.
- Errors use `{error, detail}`. `unwrap()` turns them into `ApiRequestError`, and `QueryState` renders them.

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
