// Mock transport for openapi-fetch: answers every contract-v1 endpoint from synthetic fixtures.
import { CLASSIFY_MAX_UPLOAD_BYTES } from "@/api/client";
import type { CampaignDetail, CampaignSummary, ClassifyResult, EdgeDecisionRequest, MergeRequest, Outcome, SplitRequest } from "@/api/types";
import * as db from "./data";
import { MOCK_CAMPAIGN_FAIL_ID, MOCK_EDGE_FAIL_ID } from "./sentinels";

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
const notImplemented = () => new HttpError(501, "not_implemented", "Analyst overrides are enabled after core freeze.");
const RECORDED_AT = "2026-11-21T22:00:00Z";

async function readJson<T>(req: Request): Promise<T> {
  return (await req.json()) as T;
}

function toSummary(detail: CampaignDetail): CampaignSummary {
  return {
    id: detail.id,
    label: detail.label,
    level: detail.level,
    size: detail.size,
    incident_ids: [...detail.incident_ids],
    first_seen: detail.first_seen,
    last_seen: detail.last_seen,
    strongest_evidence: detail.strongest_evidence,
    network_id: detail.network_id,
  };
}

function assignIncidents(campaignId: string, label: string, incidentIds: string[]) {
  for (const id of incidentIds) {
    const row = db.incidents.find((i) => i.id === id);
    if (!row) continue;
    row.campaign_id = campaignId;
    row.campaign_label = label;
    row.status = "in_campaign";
    row.outcome = "known_campaign";
  }
}

function upsertGraphCampaign(id: string, label: string, parent: string | null) {
  const existing = db.graph.nodes.find((n) => n.id === id);
  if (existing) {
    existing.label = label;
    existing.parent = parent;
    existing.kind = "campaign";
    return;
  }
  db.graph.nodes.push({ id, kind: "campaign", label, parent, outcome: null, coverage_level: null });
}

function retargetIncidentParents(incidentIds: string[], parent: string) {
  for (const n of db.graph.nodes) {
    if (n.kind === "incident" && incidentIds.includes(n.id)) n.parent = parent;
  }
}

/** Happy-path merge: union members, persist into db.campaigns + graph so refetch shows the change. */
function mockMerge(body: MergeRequest): CampaignDetail {
  if (body.campaign_ids.includes(MOCK_CAMPAIGN_FAIL_ID)) throw notImplemented();
  if (body.campaign_ids.length < 2) throw new HttpError(422, "validation_error", "At least two campaign_ids are required.");
  const parts = body.campaign_ids.map((id) => orNotFound(db.campaignDetail(id), "Campaign"));
  if (parts.some((p) => p.level !== "campaign")) throw new HttpError(422, "validation_error", "Only campaign-level groups can be merged.");
  const incidentIds = [...new Set(parts.flatMap((p) => p.incident_ids))];
  const base = parts[0]!;
  const merged: CampaignDetail = {
    ...base,
    id: "camp_merged_synthetic",
    label: `Merged (${parts.map((p) => p.label).join(" + ")})`,
    size: incidentIds.length,
    incident_ids: incidentIds,
    members: db.incidents.filter((i) => incidentIds.includes(i.id)),
    edges: db.edges.filter((e) => incidentIds.includes(e.source) && incidentIds.includes(e.target)),
    timeline: incidentIds.map((iid, n) => ({ date: `2026-11-0${(n % 9) + 1}T10:00:00Z`, incident_id: iid, event: "merged" })),
  };
  const remove = new Set(body.campaign_ids);
  for (let i = db.campaigns.length - 1; i >= 0; i -= 1) {
    if (remove.has(db.campaigns[i]!.id)) db.campaigns.splice(i, 1);
  }
  db.campaigns.push(toSummary(merged));
  assignIncidents(merged.id, merged.label, incidentIds);
  for (let i = db.graph.nodes.length - 1; i >= 0; i -= 1) {
    if (remove.has(db.graph.nodes[i]!.id)) db.graph.nodes.splice(i, 1);
  }
  upsertGraphCampaign(merged.id, merged.label, merged.network_id);
  retargetIncidentParents(incidentIds, merged.id);
  return merged;
}

/** Happy-path split: persist remaining + new campaign into db.campaigns + graph. */
function mockSplit(body: SplitRequest): CampaignDetail[] {
  if (body.campaign_id === MOCK_CAMPAIGN_FAIL_ID) throw notImplemented();
  const detail = orNotFound(db.campaignDetail(body.campaign_id), "Campaign");
  if (detail.level !== "campaign") throw new HttpError(422, "validation_error", "Only campaign-level groups can be split.");
  if (!body.incident_ids.length) throw new HttpError(422, "validation_error", "incident_ids must not be empty.");
  const move = new Set(body.incident_ids);
  if ([...move].some((id) => !detail.incident_ids.includes(id))) throw new HttpError(422, "validation_error", "incident_ids must be members of the campaign.");
  if (move.size >= detail.incident_ids.length) throw new HttpError(422, "validation_error", "Cannot move all members out of a campaign.");
  const remainingIds = detail.incident_ids.filter((id) => !move.has(id));
  const movedIds = detail.incident_ids.filter((id) => move.has(id));
  const remaining: CampaignDetail = {
    ...detail,
    size: remainingIds.length,
    incident_ids: remainingIds,
    members: detail.members.filter((m) => remainingIds.includes(m.id)),
    edges: detail.edges.filter((e) => remainingIds.includes(e.source) && remainingIds.includes(e.target)),
    timeline: remainingIds.map((iid, n) => ({ date: `2026-11-0${(n % 9) + 1}T10:00:00Z`, incident_id: iid, event: "retained" })),
  };
  const created: CampaignDetail = {
    ...detail,
    id: "camp_split_synthetic",
    label: `${detail.label} (split)`,
    size: movedIds.length,
    incident_ids: movedIds,
    members: detail.members.filter((m) => movedIds.includes(m.id)),
    edges: detail.edges.filter((e) => movedIds.includes(e.source) && movedIds.includes(e.target)),
    timeline: movedIds.map((iid, n) => ({ date: `2026-11-0${(n % 9) + 1}T10:00:00Z`, incident_id: iid, event: "split out" })),
  };
  const idx = db.campaigns.findIndex((c) => c.id === body.campaign_id);
  if (idx >= 0) db.campaigns[idx] = toSummary(remaining);
  else db.campaigns.push(toSummary(remaining));
  db.campaigns.push(toSummary(created));
  assignIncidents(remaining.id, remaining.label, remainingIds);
  assignIncidents(created.id, created.label, movedIds);
  upsertGraphCampaign(remaining.id, remaining.label, remaining.network_id);
  upsertGraphCampaign(created.id, created.label, created.network_id);
  retargetIncidentParents(remainingIds, remaining.id);
  retargetIncidentParents(movedIds, created.id);
  return [remaining, created];
}

async function mockEdgeDecision(edgeId: string, req: Request) {
  if (edgeId === MOCK_EDGE_FAIL_ID) throw notImplemented();
  const known = db.edges.some((e) => e.id === edgeId) || edgeId.startsWith("edge_");
  if (!known && edgeId !== "edge_demo") throw notFound("Edge");
  const body = await readJson<EdgeDecisionRequest>(req);
  if (body.decision !== "confirm" && body.decision !== "reject") {
    throw new HttpError(422, "validation_error", "decision must be confirm or reject.");
  }
  return { edge_id: edgeId, decision: body.decision, recorded_at: RECORDED_AT };
}

/** After POST /api/import, the next few GET /api/runs/{id} responses look "running" so the Overview progress UI can be exercised. */
let importPollsLeft = 0;

/** Clears in-memory mock run progress and restore mutable fixtures between tests. */
export function resetMockState() {
  importPollsLeft = 0;
  db.resetMutableFixtures();
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

/** Stand-in for the backend's salted ref: a stable 16-hex digest, so mock exports never carry internal ids. */
function maskedRef(kind: string, id: string): string {
  let h = 0xcbf29ce484222325n;
  for (const ch of `${kind}:${id}`) h = BigInt.asUintN(64, (h ^ BigInt(ch.codePointAt(0)!)) * 0x100000001b3n);
  return `${kind}-${h.toString(16).padStart(16, "0")}`;
}

/** Mock-mode export file: synthetic, masked-style content with the backend's content type and attachment filename. */
function syntheticExport(campaign: NonNullable<ReturnType<typeof db.campaignDetail>>, ext: string): Response {
  if (campaign.level !== "campaign") throw notFound("Campaign"); // the backend exports campaign-level groups only
  const ref = maskedRef("campaign", campaign.id);
  const rows = campaign.members.map((m) => `incident,${ref},${maskedRef("incident", m.id)}`);
  const body =
    ext === "csv" ? `record_type,campaign_ref,incident_ref\n${rows.join("\n")}\n`
    : ext === "html" ? `<!doctype html><title>Synthetic evidence pack</title><h1>${ref} (synthetic, mock mode)</h1>`
    : JSON.stringify({ Event: { info: `${ref} (synthetic, mock mode)`, Attribute: [] } });
  const type = ext === "csv" ? "text/csv; charset=utf-8" : ext === "html" ? "text/html; charset=utf-8" : "application/json";
  return new Response(body, { headers: { "Content-Type": type, "Content-Disposition": `attachment; filename="scamgraph-${ref}.${ext}"` } });
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
  ["POST", /^\/api\/campaigns\/merge$/, async (_m, _u, req) => mockMerge(await readJson<MergeRequest>(req))],
  ["POST", /^\/api\/campaigns\/split$/, async (_m, _u, req) => mockSplit(await readJson<SplitRequest>(req))],
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
  ["POST", /^\/api\/edges\/([^/]+)\/decision$/, ([id], _, req) => mockEdgeDecision(id!, req)],
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
