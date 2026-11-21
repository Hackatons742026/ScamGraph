// Live smoke check (#7): every screen's GET endpoint against a running backend, validated against the
// committed OpenAPI snapshot (which must equal the live /openapi.json), plus same-origin serving of the
// built app and a few demo-quality warnings.
// Usage: npm run smoke:live   (API_URL defaults to http://localhost:8000). Prints routes, shapes and counts, never values.
import { readFileSync } from "node:fs";

const base = process.env.API_URL ?? "http://localhost:8000";
const snapshotText = readFileSync(new URL("../openapi.snapshot.json", import.meta.url), "utf8");
const spec = JSON.parse(snapshotText);
const failures = [];
const warnings = [];
const list = (x) => (Array.isArray(x) ? x : []);

const resolve = (s) => (s?.$ref ? spec.components.schemas[s.$ref.split("/").pop()] : s);
const isType = {
  string: (v) => typeof v === "string",
  integer: (v) => Number.isInteger(v),
  number: (v) => typeof v === "number" && Number.isFinite(v),
  boolean: (v) => typeof v === "boolean",
  null: (v) => v === null,
  array: (v) => Array.isArray(v),
  object: (v) => v !== null && typeof v === "object" && !Array.isArray(v),
};

/** Structural check: required keys, primitive types, nullability, enums, array items, additionalProperties. */
function check(schema, value, path) {
  const s = resolve(schema);
  if (!s || Object.keys(s).length === 0) return;
  const options = s.anyOf ?? s.oneOf;
  if (options) {
    if (value === null && options.some((o) => o.type === "null")) return;
    return check(options.find((o) => o.type !== "null"), value, path);
  }
  if (s.enum && !s.enum.includes(value)) return failures.push(`${path}: value (${typeof value}) not in enum`);
  const types = [s.type ?? (s.properties ? "object" : undefined)].flat().filter(Boolean);
  if (types.length && !types.some((t) => isType[t]?.(value))) return failures.push(`${path}: expected ${types.join("|")}, got ${Array.isArray(value) ? "array" : value === null ? "null" : typeof value}`);
  if (Array.isArray(value)) value.slice(0, 20).forEach((v, i) => check(s.items, v, `${path}[${i}]`));
  else if (isType.object(value)) {
    for (const key of s.required ?? []) if (!(key in value)) failures.push(`${path}.${key}: missing`);
    for (const [key, sub] of Object.entries(s.properties ?? {})) if (key in value) check(sub, value[key], `${path}.${key}`);
    if (s.additionalProperties && typeof s.additionalProperties === "object")
      for (const [key, v] of Object.entries(value)) if (!(key in (s.properties ?? {}))) check(s.additionalProperties, v, `${path}.${key}`);
  }
}

/** The GET operation for a concrete route: exact paths win over templated ones (/api/runs/latest before /api/runs/{run_id}). */
function operationFor(route) {
  const path = route.split("?")[0];
  const candidates = Object.entries(spec.paths)
    .filter(([p, ops]) => ops.get && new RegExp(`^${p.replace(/\{[^}]+\}/g, "[^/]+")}$`).test(path))
    .sort(([a], [b]) => (a.match(/\{/g)?.length ?? 0) - (b.match(/\{/g)?.length ?? 0));
  return candidates[0]?.[1].get;
}

async function get(route, status = 200, schemaOverride = undefined) {
  const res = await fetch(base + route);
  if (res.status !== status) {
    failures.push(`GET ${route}: HTTP ${res.status}, expected ${status}`);
    return null;
  }
  const body = res.headers.get("content-type")?.includes("json") ? await res.json() : await res.text();
  const schema = schemaOverride ?? operationFor(route)?.responses?.[String(status)]?.content?.["application/json"]?.schema;
  if (!schema) failures.push(`GET ${route}: no ${status} JSON schema in the snapshot`);
  else check(schema, body, route);
  return body;
}

async function main() {
  try {
    await fetch(`${base}/api/health`);
  } catch {
    console.log(`FAIL  backend unreachable at ${base} (start uvicorn, or set API_URL)`);
    process.exit(2);
  }
  const live = await fetch(`${base}/openapi.json`).then((r) => r.json());
  if (JSON.stringify(live) !== JSON.stringify(spec)) failures.push("openapi.snapshot.json differs from the live /openapi.json: run npm run gen:api:live");

  const enc = encodeURIComponent;
  await get("/api/health");
  const latest = await fetch(`${base}/api/runs/latest`);
  if (latest.status === 404) warnings.push("no import run yet: /api/runs/latest is 404 (Overview shows the pre-import state)");
  else await get("/api/runs/latest");
  const incidents = list(await get("/api/incidents"));
  const detail = incidents[0] ? await get(`/api/incidents/${enc(incidents[0].id)}`) : null;
  const artifact = list(detail?.artifacts)[0];
  if (artifact) await get(`/api/artifacts/${enc(artifact.id)}`);
  await get("/api/incidents?status=needs_review,unassigned");
  const campaigns = list(await get("/api/campaigns"));
  if (campaigns[0]) {
    await get(`/api/campaigns/${enc(campaigns[0].id)}`);
    await get(`/api/campaigns/${enc(campaigns[0].id)}/links`);
    await get(`/api/graph?campaign=${enc(campaigns[0].id)}`);
  }
  const graph = await get("/api/graph");
  await get("/api/graph?tiers=A,B&levels=campaign");
  await get("/api/eval/report");
  await get("/api/does-not-exist", 404, { $ref: "#/components/schemas/ErrorResponse" }); // contract {error, detail}
  const shell = await fetch(`${base}/graph`);
  if (!shell.ok || !shell.headers.get("content-type")?.includes("text/html")) failures.push("GET /graph: built app not served same-origin (run npm run build)");

  // Demo-quality warnings: the UI works, but these make the screens hard to read.
  const nodes = list(graph?.nodes);
  const edges = list(graph?.edges);
  if (incidents.length > 1 && new Set(incidents.map((i) => i?.label)).size === 1) warnings.push("every incident has the same label");
  if (campaigns.some((c) => c?.label === c?.id)) warnings.push("campaign labels are raw ids");
  if (campaigns.length && campaigns.every((c) => c?.strongest_evidence == null)) warnings.push("no campaign has strongest_evidence");
  if (nodes.length && !nodes.some((n) => n?.kind !== "incident")) warnings.push("graph has no campaign/network/unassigned group nodes");
  if (edges.length && edges.every((e) => list(e?.evidence).length === 0)) warnings.push("no graph edge carries evidence (side panel will be empty)");

  console.log(`live smoke against ${base}: ${incidents.length} incidents, ${campaigns.length} campaigns, ${edges.length} links`);
  for (const w of warnings) console.log(`WARN  ${w}`);
  for (const f of failures) console.log(`FAIL  ${f}`);
  console.log(failures.length ? `${failures.length} contract failure(s)` : "OK: every endpoint matches the OpenAPI snapshot, which matches the live backend");
  process.exit(failures.length ? 1 : 0);
}

await main();
