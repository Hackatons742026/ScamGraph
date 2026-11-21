// Aliases over the generated OpenAPI types (src/api/schema.d.ts, `npm run gen:api`).
// Never hand-write a contract type: add an alias here instead.
import type { components } from "./schema";

type S = components["schemas"];

export type Tier = S["Tier"];
export type Family = S["Family"];
export type Level = S["Level"];
export type Outcome = S["Outcome"];
export type IncidentStatus = S["IncidentStatus"];
export type ArtifactKind = S["ArtifactKind"];
export type ParseStatus = S["ParseStatus"];
export type FunnelRole = S["FunnelRole"];
export type CoverageLevel = S["CoverageLevel"];
export type RunStatus = S["RunStatus"];

export type ApiError = S["ErrorResponse"];
export type EvidenceItem = S["EvidenceItem"];
export type Coverage = S["Coverage"];
export type Reason = S["Reason"];
export type Decision = S["Decision"];
export type Edge = S["Edge"];
export type ArtifactSummary = S["ArtifactSummary"];
export type ArtifactDetail = S["ArtifactDetail"];
export type RedirectHop = S["RedirectHop"];
export type FunnelStep = S["FunnelStep"];
export type Media = S["Media"];
export type IncidentSummary = S["IncidentSummary"];
export type IncidentDetail = S["IncidentDetail"];
export type CampaignSummary = S["CampaignSummary"];
export type CampaignDetail = S["CampaignDetail"];
export type CampaignLink = S["CampaignLink"];
export type GraphNode = S["GraphNode"];
export type GraphResponse = S["GraphResponse"];
export type RunSummary = S["RunSummary"];
export type ClassifyResult = S["ClassifyResult"];
export type EvalReport = S["EvalReport"];
