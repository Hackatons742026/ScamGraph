// Synthetic fixtures shaped by contract v1. NO real dataset content: fake domains (*.example-scam.test),
// TEST-NET IPs, invented IDs. Typed against the generated schema so contract drift breaks the build.
import type {
  ArtifactDetail,
  ArtifactSummary,
  CampaignDetail,
  CampaignLink,
  CampaignSummary,
  Coverage,
  Edge,
  EvalReport,
  EvidenceItem,
  GraphResponse,
  IncidentDetail,
  IncidentSummary,
  RunSummary,
} from "@/api/types";

const ev = (id: string, p: Partial<EvidenceItem> & Pick<EvidenceItem, "type" | "tier" | "display">): EvidenceItem => ({
  id, family: null, weight: 1, artifact_id: "art_alpha1_har", funnel_step: 1, ignored: false,
  ignore_reason: null, detail: null, ...p,
});

export const evidence = {
  pixel: ev("ev_pixel", { type: "pixel_id", tier: "A", display: "pixel_****1111", weight: 2.3, detail: "exact salted-hash match" }),
  kit: ev("ev_kit", { type: "kit_api_path", tier: "B", family: "kit", display: "/api/v1/…/{id}", weight: 0.9, artifact_id: "art_alpha2_har", funnel_step: 2 }),
  creative: ev("ev_creative", { type: "image_phash", tier: "B", family: "creative", display: "3 identical content images", weight: 1.4, artifact_id: "art_beta1_page", detail: "pHash distance 2" }),
  domain: ev("ev_domain", { type: "landing_domain", tier: "B", family: "domain", display: "offer.example-scam.test", weight: 1.1, artifact_id: "art_beta1_page" }),
  sentence: ev("ev_sentence", { type: "shared_sentence", tier: "C", display: "“…” (12 shared words)", weight: 0.4, detail: "text sim 0.81" }),
  tds: ev("ev_tds", { type: "click_domain", tier: "B", family: "tds", display: "click.example-scam.test", weight: 0.6, artifact_id: "art_alpha2_har", funnel_step: 2 }),
  cdn: ev("ev_cdn", { type: "server_ip", tier: "B", family: "hosting", display: "203.0.113.x", weight: 0, ignored: true, ignore_reason: "cdn_ip" }),
  phone: ev("ev_phone", { type: "phone", tier: "A", display: "+48 *** *** 000", weight: 0, artifact_id: "art_gamma_page", ignored: true, ignore_reason: "placeholder_phone" }),
} satisfies Record<string, EvidenceItem>;

const cov = (kinds: Coverage["artifact_kinds"], badges: string[] = []): Coverage => ({
  artifact_kinds: kinds, has_har: kinds.includes("har"), has_page: kinds.includes("html") || kinds.includes("mhtml"),
  has_image: kinds.includes("image"), has_video: kinds.includes("video"), has_adlib: kinds.includes("adlib_json"),
  has_text: kinds.some((k) => k !== "video"), level: badges.length ? "low" : "ok", badges,
});

const inc = (p: Partial<IncidentSummary> & Pick<IncidentSummary, "id" | "label" | "status">): IncidentSummary => ({
  first_seen: "2026-11-01T10:00:00Z", last_seen: "2026-11-03T18:00:00Z", artifact_count: 3,
  coverage: cov(["har", "html", "image"]), campaign_id: null, campaign_label: null, network_id: null,
  outcome: null, reason_summary: null, ingested_at: null, ...p,
});

export const incidents: IncidentSummary[] = [
  inc({ id: "inc_alpha_1", label: "Synthetic incident Alpha-1", status: "in_campaign", campaign_id: "camp_alpha", campaign_label: "Synthetic Campaign Alpha", network_id: "net_kit", outcome: "known_campaign", reason_summary: "Shares a tier-A ad-tracking pixel with Alpha-2.", ingested_at: "2026-11-04T10:15:00Z" }),
  inc({ id: "inc_alpha_2", label: "Synthetic incident Alpha-2", status: "in_campaign", artifact_count: 4, coverage: cov(["har", "html"]), campaign_id: "camp_alpha", campaign_label: "Synthetic Campaign Alpha", network_id: "net_kit", outcome: "known_campaign", reason_summary: "Shares a tier-A ad-tracking pixel with Alpha-1." }),
  inc({ id: "inc_beta_1", label: "Synthetic incident Beta-1", status: "in_campaign", campaign_id: "camp_beta", campaign_label: "Synthetic Campaign Beta", network_id: "net_kit", outcome: "known_campaign", reason_summary: "Two tier-B families (creative + domain) shared with Beta-2." }),
  inc({ id: "inc_beta_2", label: "Synthetic incident Beta-2", status: "in_campaign", artifact_count: 5, campaign_id: "camp_beta", campaign_label: "Synthetic Campaign Beta", network_id: "net_kit", outcome: "known_campaign", reason_summary: "Two tier-B families (creative + domain) shared with Beta-1." }),
  inc({ id: "inc_gamma", label: "Synthetic incident Gamma", status: "new_candidate", outcome: "new_candidate", reason_summary: "Enough coverage, but no campaign-level link." }),
  inc({ id: "inc_delta", label: "Synthetic incident Delta", status: "needs_review", artifact_count: 2, coverage: cov(["video", "adlib_json"], ["no HAR", "video only"]), outcome: "needs_review", reason_summary: "Only one comparable evidence type." }),
  inc({ id: "inc_epsilon", label: "Synthetic incident Epsilon", status: "unassigned", artifact_count: 2, coverage: cov(["html", "image"], ["no HAR"]), reason_summary: "No campaign-level evidence; kept unassigned." }),
];

const edge = (id: string, source: string, target: string, p: Partial<Edge> & Pick<Edge, "level" | "tier" | "evidence">): Edge => ({
  id, source, target, families: [], score: 1, comparable: 4, low_confidence: false, ...p,
});

export const edges: Edge[] = [
  edge("edge_alpha", "inc_alpha_1", "inc_alpha_2", { level: "campaign", tier: "A", score: 3.1, comparable: 5, evidence: [evidence.pixel, evidence.sentence, evidence.cdn] }),
  edge("edge_beta", "inc_beta_1", "inc_beta_2", { level: "campaign", tier: "B", families: ["creative", "domain"], score: 2.5, evidence: [evidence.creative, evidence.domain] }),
  edge("edge_kit", "inc_alpha_2", "inc_beta_1", { level: "network", tier: "B", families: ["kit"], score: 0.9, comparable: 3, evidence: [evidence.kit] }),
  edge("edge_weak", "inc_alpha_2", "inc_gamma", { level: "network", tier: "B", families: ["tds"], score: 0.6, comparable: 1, low_confidence: true, evidence: [evidence.tds, evidence.phone] }),
];

const art = (id: string, p: Partial<ArtifactSummary> & Pick<ArtifactSummary, "kind" | "name_display">): ArtifactSummary => ({
  id, funnel_step: null, role: null, parse_status: "ok", error: null, captured_at: "2026-11-01T10:00:00Z",
  duplicate_of: null, observations: 1, ...p,
});

const artifactsByIncident: Record<string, ArtifactSummary[]> = {
  inc_alpha_1: [art("art_alpha1_shot", { kind: "image", name_display: "ad_screenshot.png", funnel_step: 0, role: "ad" }), art("art_alpha1_har", { kind: "har", name_display: "capture.har", funnel_step: 1, role: "prelander" }), art("art_alpha1_page", { kind: "html", name_display: "article.html", funnel_step: 1, role: "prelander", observations: 2 })],
  inc_alpha_2: [art("art_alpha2_har", { kind: "har", name_display: "step_2.har", funnel_step: 2, role: "offer" }), art("art_alpha2_page", { kind: "html", name_display: "article.html", funnel_step: 1, role: "prelander", duplicate_of: "art_alpha1_page" }), art("art_alpha2_bad", { kind: "unknown", name_display: "broken.bin", parse_status: "failed", error: "Unrecognised format (logged and skipped)" })],
  inc_delta: [art("art_delta_video", { kind: "video", name_display: "screen_recording.mp4", funnel_step: 0, role: "ad" }), art("art_delta_adlib", { kind: "adlib_json", name_display: "ad.info.json", funnel_step: 0, role: "ad" })],
};

export function incidentDetail(id: string): IncidentDetail | undefined {
  const summary = incidents.find((i) => i.id === id);
  if (!summary) return undefined;
  const own = edges.filter((e) => e.source === id || e.target === id);
  const artifacts = artifactsByIncident[id] ?? [art(`art_${id}_page`, { kind: "html", name_display: "page.html", funnel_step: 1, role: "offer" })];
  return {
    ...summary,
    artifacts,
    funnel: artifacts.some((a) => a.kind === "har")
      ? [
          { step: 1, role: "prelander", artifact_ids: [artifacts[0]!.id], domain_display: "news.example-scam.test", redirect_chain: [{ seq: 1, url_display: "https://news.example-scam.test/a?fbclid=[redacted]", status: 302, kind: "3xx" }, { seq: 2, url_display: "https://click.example-scam.test/click", status: 200, kind: "js" }] },
          { step: 2, role: "offer", artifact_ids: [artifacts[artifacts.length - 1]!.id], domain_display: "offer.example-scam.test", redirect_chain: [] },
        ]
      : [],
    evidence: [...new Map(own.flatMap((e) => e.evidence).map((e) => [e.id, e])).values()],
    decision: summary.outcome && {
      outcome: summary.outcome, campaign_id: summary.campaign_id, campaign_label: summary.campaign_label,
      reasons: [{ kind: summary.outcome === "needs_review" ? "coverage" : "match", text: summary.reason_summary ?? "", evidence: own[0]?.evidence.slice(0, 1) ?? [] }],
      decided_at: "2026-11-21T12:00:00Z",
    },
    edges: own,
  };
}

export function artifactDetail(id: string): ArtifactDetail | undefined {
  const summary = Object.values(artifactsByIncident).flat().find((a) => a.id === id);
  if (!summary) return undefined;
  const isMedia = summary.kind === "image" || summary.kind === "video";
  return {
    ...summary,
    pages: summary.kind === "html" ? [{ url_display: "https://news.example-scam.test/article", domain_display: "news.example-scam.test", title: "Synthetic article title", role: "prelander" }] : [],
    redirect_chain: summary.kind === "har" ? [{ seq: 1, url_display: "https://ad.example-scam.test/r?clickid=[redacted]", status: 302, kind: "3xx" }] : [],
    media: isMedia ? [0, 2, 4].map((t, i) => ({ id: `${id}_m${i}`, kind: summary.kind === "video" ? "frame" : "screenshot", frame_ts: summary.kind === "video" ? t : null, ocr_text: "Synthetic OCR text (Polish sample: „Zarabiaj więcej”)", width: 720, height: 405 })) : [],
    ocr_text: isMedia ? "Synthetic OCR text" : null,
    request_count: summary.kind === "har" ? 42 : 0,
    hosts_display: summary.kind === "har" ? ["news.example-scam.test", "click.example-scam.test", "cdn.example.test"] : [],
  };
}

const camp = (id: string, label: string, ids: string[], strongest: EvidenceItem): CampaignSummary => ({
  id, label, level: "campaign", size: ids.length, incident_ids: ids, first_seen: "2026-11-01T10:00:00Z",
  last_seen: "2026-11-03T18:00:00Z", strongest_evidence: strongest, network_id: "net_kit", membership_source: "automatic",
});

function cloneCampaigns(rows: CampaignSummary[]): CampaignSummary[] {
  return rows.map((c) => ({ ...c, incident_ids: [...c.incident_ids] }));
}

const CAMPAIGNS_SEED: CampaignSummary[] = [
  camp("camp_alpha", "Synthetic Campaign Alpha", ["inc_alpha_1", "inc_alpha_2"], evidence.pixel),
  camp("camp_beta", "Synthetic Campaign Beta", ["inc_beta_1", "inc_beta_2"], evidence.creative),
  { ...camp("net_kit", "Synthetic shared-kit network", ["inc_alpha_1", "inc_alpha_2", "inc_beta_1", "inc_beta_2"], evidence.kit), level: "network", network_id: null },
];

/** Mutable campaign list — merge/split mocks persist here so invalidate + refetch shows a change. */
export const campaigns: CampaignSummary[] = cloneCampaigns(CAMPAIGNS_SEED);

const INCIDENT_CAMPAIGN_SEED = incidents.map((i) => ({
  id: i.id,
  campaign_id: i.campaign_id,
  campaign_label: i.campaign_label,
  status: i.status,
  outcome: i.outcome,
}));

export function campaignDetail(id: string): CampaignDetail | undefined {
  const c = campaigns.find((x) => x.id === id);
  if (!c) return undefined;
  return {
    ...c,
    members: incidents.filter((i) => c.incident_ids.includes(i.id)),
    edges: edges.filter((e) => c.incident_ids.includes(e.source) && c.incident_ids.includes(e.target)),
    timeline: c.incident_ids.map((iid, n) => ({ date: `2026-11-0${n + 1}T10:00:00Z`, incident_id: iid, event: "first seen" })),
  };
}

export function campaignLinks(id: string): CampaignLink[] {
  if (id === "camp_alpha") return [{ other_id: "camp_beta", other_label: "Synthetic Campaign Beta", level: "network", shared_evidence: [evidence.kit] }];
  if (id === "camp_beta") return [{ other_id: "camp_alpha", other_label: "Synthetic Campaign Alpha", level: "network", shared_evidence: [evidence.kit] }];
  return [];
}

const GRAPH_NODES_SEED: GraphResponse["nodes"] = [
  { id: "net_kit", kind: "network", label: "Shared-kit network", parent: null, outcome: null, coverage_level: null },
  { id: "camp_alpha", kind: "campaign", label: "Campaign Alpha", parent: "net_kit", outcome: null, coverage_level: null },
  { id: "camp_beta", kind: "campaign", label: "Campaign Beta", parent: "net_kit", outcome: null, coverage_level: null },
  { id: "unassigned", kind: "unassigned", label: "Unassigned", parent: null, outcome: null, coverage_level: null },
  ...incidents.map((i) => ({ id: i.id, kind: "incident" as const, label: i.label.replace("Synthetic incident ", ""), parent: i.campaign_id ?? "unassigned", outcome: i.outcome, coverage_level: i.coverage.level })),
];

export const graph: GraphResponse = {
  nodes: GRAPH_NODES_SEED.map((n) => ({ ...n })),
  edges,
};

/** Restores campaigns / incident membership / graph nodes after mock merge/split mutations. */
export function resetMutableFixtures() {
  campaigns.splice(0, campaigns.length, ...cloneCampaigns(CAMPAIGNS_SEED));
  for (const edge of edges) delete edge.analyst_override;
  for (const seed of INCIDENT_CAMPAIGN_SEED) {
    const row = incidents.find((i) => i.id === seed.id);
    if (!row) continue;
    row.campaign_id = seed.campaign_id;
    row.campaign_label = seed.campaign_label;
    row.status = seed.status;
    row.outcome = seed.outcome;
  }
  graph.nodes.splice(0, graph.nodes.length, ...GRAPH_NODES_SEED.map((n) => ({ ...n })));
}

const artifactsByKind: RunSummary["artifacts_by_kind"] = {
  har: { total: 4, parsed: 4, failed: 0, partial: 0 }, html: { total: 5, parsed: 5, failed: 0, partial: 0 },
  image: { total: 4, parsed: 4, failed: 0, partial: 0 }, video: { total: 1, parsed: 1, failed: 0, partial: 1 },
  adlib_json: { total: 1, parsed: 1, failed: 0, partial: 0 }, unknown: { total: 1, parsed: 0, failed: 1, partial: 0 },
};
const totalArtifacts = Object.values(artifactsByKind).reduce((n, k) => n + k.total, 0);
const countStatus = (s: IncidentSummary["status"]) => incidents.filter((i) => i.status === s).length;

// Counts are derived from the fixtures so every screen shows the same numbers.
export const latestRun: RunSummary = {
  id: "run_mock_001", status: "done", started_at: "2026-11-21T15:00:00Z", finished_at: "2026-11-21T15:00:42Z",
  incidents: incidents.length, artifacts: totalArtifacts, artifacts_by_kind: artifactsByKind,
  unique_artifacts: totalArtifacts - 1, duplicates: 1,
  campaigns: campaigns.filter((c) => c.level === "campaign").length, networks: campaigns.filter((c) => c.level === "network").length,
  unassigned: incidents.filter((i) => !i.campaign_id).length, needs_review: countStatus("needs_review"), new_candidates: countStatus("new_candidate"),
  secrets_redacted: 9, error: null,
};

const metrics = (tp: number, fp: number, fn: number) => {
  const precision = tp / (tp + fp);
  const recall = tp / (tp + fn);
  return { precision, recall, f1: (2 * precision * recall) / (precision + recall), tp, fp, fn };
};

const OUTCOMES = ["known_campaign", "new_candidate", "needs_review"] as const;
const looRows = incidents.map((i) => {
  const expected = i.outcome ?? "needs_review";
  // One deliberate synthetic miss so the confusion matrix shows an error cell.
  const predicted = i.status === "new_candidate" ? "needs_review" : expected;
  return { incident_id: i.id, expected, predicted, correct: expected === predicted };
});

export const evalReport: EvalReport = {
  generated_at: "2026-11-21T15:05:00Z",
  scenarios: ["Exact duplicates", "Modified versions", "Known campaigns", "Correct non-merging", "New material", "Missing metadata", "Different formats"].map((name, i) => ({
    id: (i + 1) as EvalReport["scenarios"][number]["id"], name, criterion: "Synthetic criterion", passed: i !== 5, details: i === 5 ? "Synthetic failure detail" : "Synthetic pass",
  })),
  pairs: { n_pairs: 15, mentor_verified: 5, agreement: 0.8, campaign: metrics(4, 0, 1), network: metrics(3, 1, 0) },
  false_merges: 0,
  loo: {
    accuracy: looRows.filter((r) => r.correct).length / looRows.length,
    rows: looRows,
    confusion: {
      labels: [...OUTCOMES],
      matrix: OUTCOMES.map((exp) => OUTCOMES.map((pred) => looRows.filter((r) => r.expected === exp && r.predicted === pred).length)),
    },
  },
  ablation: [
    { config: "Content only", campaign_p: 0.5, campaign_r: 0.5, false_merges: 2, loo_routing: 0.5 },
    { config: "+ tier A identifiers (full)", campaign_p: 1, campaign_r: 0.8, false_merges: 0, loo_routing: 0.83 },
  ],
};
