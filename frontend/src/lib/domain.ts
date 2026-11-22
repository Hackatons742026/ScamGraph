// Single source for user-facing domain labels and colours (UI language: English).
// Colours are hex so Cytoscape (fe-4) can use the same values as the badges.
import type { Family, IncidentStatus, Outcome, RunStatus, Tier } from "@/api/types";

/** Evidence type keys (snake_case from the API) as readable text. */
export const humanize = (s: string): string => s.replace(/_/g, " ");

/** Deterministic date for tables (no locale/timezone drift): YYYY-MM-DD or an em dash. */
export const formatDate = (iso: string | null): string => (iso ? iso.slice(0, 10) : "—");

/** Format an RFC 3339 timestamp in the viewer's browser locale and timezone. */
/** Host and path of a (redacted) URL; tracking query strings stay in the tooltip. */
export function shortUrl(url: string, max = 80): string {
  let text = url;
  try {
    const parsed = new URL(url);
    text = `${parsed.host}${parsed.pathname === "/" ? "" : parsed.pathname}${parsed.search ? "?…" : ""}`;
  } catch {
    // Not an absolute URL: show it as given.
  }
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

export function formatTimestamp(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (!Number.isFinite(date.getTime())) return "—";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

export const TIER: Record<Tier, { label: string; hint: string; color: string }> = {
  A: { label: "Tier A", hint: "Unique identifier: links incidents on its own", color: "#b91c1c" },
  B: { label: "Tier B", hint: "Shared infrastructure or kit: needs two families for a campaign link", color: "#1d4ed8" },
  C: { label: "Tier C", hint: "Weak content signal: adds to the score only", color: "#64748b" },
};

export const FAMILY: Record<NonNullable<Family>, { label: string; color: string }> = {
  kit: { label: "Site kit", color: "#7c3aed" },
  tds: { label: "Click tracking (TDS)", color: "#ea580c" },
  domain: { label: "Domain", color: "#0d9488" },
  creative: { label: "Creative", color: "#db2777" },
  hosting: { label: "Hosting", color: "#475569" },
};

export const OUTCOME: Record<Outcome, string> = {
  known_campaign: "Known Campaign",
  new_candidate: "New Campaign Candidate",
  needs_review: "Needs Review",
};

export const STATUS: Record<IncidentStatus, string> = {
  in_campaign: "In campaign",
  unassigned: "Unassigned",
  needs_review: "Needs Review",
  new_candidate: "New Candidate",
};

export const RUN_STATUS: Record<RunStatus, string> = {
  pending: "Pending",
  running: "Running",
  done: "Done",
  failed: "Failed",
};

const IGNORE_REASON: Record<string, string> = {
  cdn_ip: "CDN / shared-hosting IP",
  public_lib: "Public library",
  placeholder_phone: "Placeholder phone number",
  small_doc: "Helper document < 5 KB",
  high_df: "Too common (> 30% of incidents)",
  platform_domain: "Shared platform domain (not operator infrastructure)",
  placeholder_email: "Placeholder e-mail address",
  other: "Ignored by rule",
};

/** Human label for EvidenceItem.ignore_reason (optional in the live OpenAPI); unknown future reasons fall back to a generic label. */
export function ignoreReasonLabel(reason: string | null | undefined): string | null {
  if (!reason) return null;
  return IGNORE_REASON[reason] ?? "Ignored by rule";
}
