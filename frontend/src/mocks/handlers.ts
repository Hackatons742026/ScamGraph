// Mock transport for openapi-fetch: answers every contract-v1 endpoint from synthetic fixtures.
import { CLASSIFY_MAX_UPLOAD_BYTES } from "@/api/client";
import type { ClassifyResult, Outcome } from "@/api/types";
import * as db from "./data";

type Handler = (match: string[], url: URL, req: Request) => unknown | Promise<unknown>;

class HttpError {
  constructor(readonly status: number, readonly error: string, readonly detail: string) {}
}
const notFound = (what: string) => new HttpError(404, "not_found", `${what} not found`);
const orNotFound = <T>(value: T | undefined, what: string): T => {
  if (value === undefined) throw notFound(what);
  return value;
};
const csv = (url: URL, key: string) => url.searchParams.get(key)?.split(",").filter(Boolean) ?? [];

/** After POST /api/import, the next few GET /api/runs/{id} responses look "running" so the Overview progress UI can be exercised. */
let importPollsLeft = 0;

/** Clears in-memory mock run progress between tests. */
export function resetMockState() {
  importPollsLeft = 0;
}

function runSnapshot() {
  if (importPollsLeft > 0) {
    importPollsLeft -= 1;
    return { ...db.latestRun, status: "running" as const, finished_at: null, error: null };
  }
  return db.latestRun;
}

async function classify(req: Request): Promise<ClassifyResult> {
  const form = await req.formData();
  const files = form.getAll("files").filter((f): f is File => typeof f !== "string");
  const totalBytes = files.reduce((sum, f) => sum + f.size, 0);
  if (totalBytes > CLASSIFY_MAX_UPLOAD_BYTES) {
    throw new HttpError(413, "payload_too_large", "Upload exceeds the size limit");
  }
  const text = form.get("text");
  const url = form.get("url");
  const exclude = form.get("exclude_incident");
  if (!files.length && !text && !url) {
    throw new HttpError(422, "validation_error", "At least one file, text, or URL is required.");
  }
  const left = typeof exclude === "string" ? db.incidents.find((i) => i.id === exclude) : undefined;
  const videoOnly = files.length > 0 && files.every((f) => f.type.startsWith("video/"));
  const outcome: Outcome = left?.outcome ?? (videoOnly ? "needs_review" : "new_candidate");
  const reasonText: Record<Outcome, string> = {
    known_campaign: `Tier-A match to ${left?.campaign_label ?? "a known campaign"} (synthetic).`,
    new_candidate: "Two comparable evidence types, but no campaign-level link (synthetic).",
    needs_review: "Only one evidence type is comparable (synthetic).",
  };
  return {
    outcome,
    campaign_id: outcome === "known_campaign" ? (left?.campaign_id ?? null) : null,
    campaign_label: outcome === "known_campaign" ? (left?.campaign_label ?? null) : null,
    reasons: [{ kind: outcome === "needs_review" ? "coverage" : outcome === "known_campaign" ? "match" : "weak", text: reasonText[outcome], evidence: outcome === "known_campaign" ? [db.evidence.pixel] : [] }],
    // Low coverage only for needs_review; a new candidate needs enough comparable evidence by definition.
    coverage: left?.coverage ?? db.incidents.find((i) => i.status === outcome)!.coverage,
    evidence: outcome === "known_campaign" ? [db.evidence.pixel, db.evidence.sentence] : [],
    candidate_edges: outcome === "known_campaign" ? db.edges.slice(0, 1) : [],
    elapsed_ms: 84,
  };
}

/** Mock-mode export file: synthetic content with the backend's content type and attachment filename. */
function syntheticExport(campaign: NonNullable<ReturnType<typeof db.campaignDetail>>, ext: string): Response {
  const members = campaign.members.map((m) => m.id);
  const body =
    ext === "csv" ? `campaign_ref,incident_ref\n${members.map((m) => `${campaign.id},${m}`).join("\n")}\n`
    : ext === "html" ? `<!doctype html><title>Synthetic evidence pack</title><h1>${campaign.label} (synthetic, mock mode)</h1>`
    : JSON.stringify({ Event: { info: `${campaign.label} (synthetic, mock mode)`, Attribute: [] } });
  const type = ext === "csv" ? "text/csv; charset=utf-8" : ext === "html" ? "text/html; charset=utf-8" : "application/json";
  return new Response(body, { headers: { "Content-Type": type, "Content-Disposition": `attachment; filename="scamgraph-${campaign.id}.${ext}"` } });
}

const routes: Array<[method: string, pattern: RegExp, handler: Handler, okStatus?: number]> = [
  ["GET", /^\/api\/health$/, () => ({ status: "ok", version: "1" })],
  ["POST", /^\/api\/import$/, () => {
    // Two "running" polls in tests; a few more outside tests so the progress label is visible.
    importPollsLeft = import.meta.env.MODE === "test" ? 2 : 4;
    return { run_id: db.latestRun.id };
  }, 202],
  ["GET", /^\/api\/runs\/latest$/, () => runSnapshot()],
  ["GET", /^\/api\/runs\/([^/]+)$/, ([id]) => (id === db.latestRun.id ? runSnapshot() : orNotFound(undefined, "Run"))],
  ["GET", /^\/api\/incidents$/, (_, url) => {
    const status = csv(url, "status");
    const campaign = url.searchParams.get("campaign");
    return db.incidents.filter((i) => (!status.length || status.includes(i.status)) && (!campaign || i.campaign_id === campaign || i.network_id === campaign));
  }],
  ["GET", /^\/api\/incidents\/([^/]+)$/, ([id]) => orNotFound(db.incidentDetail(id!), "Incident")],
  ["GET", /^\/api\/artifacts\/([^/]+)$/, ([id]) => orNotFound(db.artifactDetail(id!), "Artifact")],
  ["GET", /^\/api\/campaigns$/, () => db.campaigns],
  ["POST", /^\/api\/campaigns\/(merge|split)$/, () => { throw new HttpError(501, "not_implemented", "Analyst overrides are enabled after core freeze."); }],
  ["GET", /^\/api\/campaigns\/([^/]+)\/links$/, ([id]) => (orNotFound(db.campaignDetail(id!), "Campaign"), db.campaignLinks(id!))],
  ["GET", /^\/api\/campaigns\/([^/]+)$/, ([id]) => orNotFound(db.campaignDetail(id!), "Campaign")],
  ["GET", /^\/api\/graph$/, (_, url) => {
    const tiers = csv(url, "tiers");
    const levels = csv(url, "levels");
    const campaign = url.searchParams.get("campaign");
    let nodes = db.graph.nodes;
    if (campaign) {
      // Focus: the campaign/network, its member incidents and child groups, plus its parent network.
      // Unknown focus → empty graph (200), as the backend does.
      const focus = nodes.find((n) => n.id === campaign);
      if (!focus) return { nodes: [], edges: [] };
      const children = nodes.filter((n) => n.parent === campaign);
      const members = nodes.filter((n) => n.parent === campaign || children.some((c) => c.id === n.parent));
      const keep = new Set([focus.id, ...(focus.parent ? [focus.parent] : []), ...children.map((n) => n.id), ...members.map((n) => n.id)]);
      nodes = nodes.filter((n) => keep.has(n.id));
    }
    const ids = new Set(nodes.map((n) => n.id));
    const edges = db.graph.edges.filter(
      (e) => ids.has(e.source) && ids.has(e.target) && (!tiers.length || tiers.includes(e.tier)) && (!levels.length || levels.includes(e.level)),
    );
    return { nodes, edges };
  }],
  ["POST", /^\/api\/classify$/, (_, __, req) => classify(req)],
  ["GET", /^\/api\/eval\/report$/, () => db.evalReport],
  ["GET", /^\/api\/exports\/([A-Za-z0-9_-]{1,128})\.(html|csv|misp\.json)$/, ([id, ext]) => syntheticExport(orNotFound(db.campaignDetail(id!), "Campaign"), ext!)],
  ["POST", /^\/api\/edges\/([^/]+)\/decision$/, () => { throw new HttpError(501, "not_implemented", "Analyst overrides are enabled after core freeze."); }],
];

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

/** Drop-in `fetch` for openapi-fetch in mock mode. Small delay outside tests so loading states are visible. */
export async function mockFetch(req: Request): Promise<Response> {
  if (import.meta.env.MODE !== "test") await new Promise((r) => setTimeout(r, 200));
  const url = new URL(req.url);
  for (const [method, pattern, handler, okStatus = 200] of routes) {
    const m = url.pathname.match(pattern);
    if (!m || method !== req.method) continue;
    try {
      const body = await handler(m.slice(1), url, req);
      return body instanceof Response ? body : json(okStatus, body);
    } catch (e) {
      if (e instanceof HttpError) return json(e.status, { error: e.error, detail: e.detail });
      throw e;
    }
  }
  return json(404, { error: "not_found", detail: `No mock for ${req.method} ${url.pathname}` });
}
