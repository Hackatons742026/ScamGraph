// Single source for user-facing domain labels and colours (UI language: English).
// Colours are hex so Cytoscape (fe-4) can use the same values as the badges.
import type { Family, IncidentStatus, Outcome, Tier } from "@/api/types";

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

const IGNORE_REASON: Record<string, string> = {
  cdn_ip: "CDN / shared-hosting IP",
  public_lib: "Public library",
  placeholder_phone: "Placeholder phone number",
  small_doc: "Helper document < 5 KB",
  high_df: "Too common (> 30% of incidents)",
  other: "Ignored by rule",
};

/** Human label for EvidenceItem.ignore_reason; unknown future reasons fall back to a generic label. */
export function ignoreReasonLabel(reason: string | null): string | null {
  if (!reason) return null;
  return IGNORE_REASON[reason] ?? "Ignored by rule";
}
