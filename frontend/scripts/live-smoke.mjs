// Live smoke check (#7): every screen's GET endpoint against a running backend, validated against the
// committed OpenAPI snapshot, plus same-origin serving of the built app and a few demo-quality warnings.
// Usage: npm run smoke:live   (API_URL defaults to http://localhost:8000). Prints only shapes and counts, never values.
import { readFileSync } from "node:fs";

const base = process.env.API_URL ?? "http://localhost:8000";
const spec = JSON.parse(readFileSync(new URL("../openapi.snapshot.json", import.meta.url), "utf8"));
const failures = [];
const warnings = [];

const resolve = (s) => (s?.$ref ? spec.components.schemas[s.$ref.split("/").pop()] : s);

/** Minimal structural check: required keys, nullability, array items, enums. Enough to catch contract drift. */
function check(schema, value, path) {
  const s = resolve(schema);
  if (!s || Object.keys(s).length === 0) return;
  const options = s.anyOf ?? s.oneOf;
  if (options) {
    if (value === null && options.some((o) => o.type === "null")) return;
    return check(options.find((o) => o.type !== "null"), value, path);
  }
  if (s.enum && !s.enum.includes(value)) return failures.push(`${path}: ${JSON.stringify(value)} not in enum`);
  if (s.type === "array") {
    if (!Array.isArray(value)) return failures.push(`${path}: expected array`);
    value.slice(0, 20).forEach((v, i) => check(s.items, v, `${path}[${i}]`));
  } else if (s.type === "object" || s.properties) {
    if (value === null || typeof value !== "object") return failures.push(`${path}: expected object`);
    for (const key of s.required ?? []) if (!(key in value)) failures.push(`${path}.${key}: missing`);
    for (const [key, sub] of Object.entries(s.properties ?? {})) if (key in value) check(sub, value[key], `${path}.${key}`);
  }
}

async function get(route, status = 200) {
  const res = await fetch(base + route);
  if (res.status !== status) {
    failures.push(`GET ${route}: HTTP ${res.status}, expected ${status}`);
    return null;
  }
  const body = res.headers.get("content-type")?.includes("json") ? await res.json() : await res.text();
  const op = Object.entries(spec.paths).find(([p]) => new RegExp(`^${p.replace(/\{[^}]+\}/g, "[^/]+")}$`).test(route.split("?")[0]))?.[1]?.get;
  const schema = op?.responses?.[String(status)]?.content?.["application/json"]?.schema;
  if (schema) check(schema, body, route);
  return body;
}

const enc = encodeURIComponent;
await get("/api/health");
const run = await fetch(`${base}/api/runs/latest`).then((r) => (r.status === 404 ? null : get("/api/runs/latest")));
if (!run) warnings.push("no import run yet: /api/runs/latest is 404 (Overview shows the pre-import state)");
const incidents = (await get("/api/incidents")) ?? [];
const detail = incidents[0] ? await get(`/api/incidents/${enc(incidents[0].id)}`) : null;
if (detail?.artifacts?.[0]) await get(`/api/artifacts/${enc(detail.artifacts[0].id)}`);
await get("/api/incidents?status=needs_review,unassigned");
const campaigns = (await get("/api/campaigns")) ?? [];
if (campaigns[0]) {
  await get(`/api/campaigns/${enc(campaigns[0].id)}`);
  await get(`/api/campaigns/${enc(campaigns[0].id)}/links`);
  await get(`/api/graph?campaign=${enc(campaigns[0].id)}`);
}
const graph = await get("/api/graph");
await get("/api/graph?tiers=A,B&levels=campaign");
await get("/api/eval/report");
await get("/api/does-not-exist", 404);
const shell = await fetch(`${base}/graph`);
if (!shell.ok || !shell.headers.get("content-type")?.includes("text/html")) failures.push("GET /graph: built app not served same-origin (run npm run build)");

// Demo-quality warnings: the UI works, but these make the screens hard to read.
if (incidents.length > 1 && new Set(incidents.map((i) => i.label)).size === 1) warnings.push("every incident has the same label");
if (campaigns.some((c) => c.label === c.id)) warnings.push("campaign labels are raw ids");
if (campaigns.length && campaigns.every((c) => c.strongest_evidence === null)) warnings.push("no campaign has strongest_evidence");
if (graph?.nodes?.length && !graph.nodes.some((n) => n.kind !== "incident")) warnings.push("graph has no campaign/network/unassigned group nodes");
if (graph?.edges?.length && graph.edges.every((e) => e.evidence.length === 0)) warnings.push("no graph edge carries evidence (side panel will be empty)");

console.log(`live smoke against ${base}: ${incidents.length} incidents, ${campaigns.length} campaigns, ${graph?.edges?.length ?? 0} links`);
for (const w of warnings) console.log(`WARN  ${w}`);
for (const f of failures) console.log(`FAIL  ${f}`);
console.log(failures.length ? `${failures.length} contract failure(s)` : "OK: every endpoint matches the OpenAPI snapshot");
process.exit(failures.length ? 1 : 0);
