// Mock transport for openapi-fetch: answers every contract-v1 endpoint from synthetic fixtures.
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

async function classify(req: Request): Promise<ClassifyResult> {
  const form = await req.formData();
  const files = form.getAll("files").filter((f): f is File => typeof f !== "string");
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
    coverage: left?.coverage ?? db.incidents.find((i) => i.id === "inc_delta")!.coverage,
    evidence: outcome === "known_campaign" ? [db.evidence.pixel, db.evidence.sentence] : [],
    candidate_edges: outcome === "known_campaign" ? db.edges.slice(0, 1) : [],
    elapsed_ms: 84,
  };
}

const routes: Array<[method: string, pattern: RegExp, handler: Handler, okStatus?: number]> = [
  ["GET", /^\/api\/health$/, () => ({ status: "ok", version: "1" })],
  ["POST", /^\/api\/import$/, () => ({ run_id: db.latestRun.id }), 202],
  ["GET", /^\/api\/runs\/latest$/, () => db.latestRun],
  ["GET", /^\/api\/runs\/([^/]+)$/, ([id]) => (id === db.latestRun.id ? db.latestRun : orNotFound(undefined, "Run"))],
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
    const edges = db.graph.edges.filter((e) => (!tiers.length || tiers.includes(e.tier)) && (!levels.length || levels.includes(e.level)));
    return { ...db.graph, edges };
  }],
  ["POST", /^\/api\/classify$/, (_, __, req) => classify(req)],
  ["GET", /^\/api\/eval\/report$/, () => db.evalReport],
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
      return json(okStatus, body);
    } catch (e) {
      if (e instanceof HttpError) return json(e.status, { error: e.error, detail: e.detail });
      throw e;
    }
  }
  return json(404, { error: "not_found", detail: `No mock for ${req.method} ${url.pathname}` });
}
