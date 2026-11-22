import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router";
import { api, ApiRequestError, unwrap } from "@/api/client";
import type { IncidentDetail as IncidentDetailType } from "@/api/types";
import { CoverageBadges, OutcomeBadge, StatusBadge } from "@/components/domain/badges";
import { QueryState } from "@/components/domain/QueryState";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { campaignHref } from "@/features/campaigns/links";
import { ArtifactsSection } from "@/features/incident/ArtifactsSection";
import { DecisionCard } from "@/features/incident/DecisionCard";
import { EvidenceList } from "@/features/incident/EvidenceList";
import { shortUrl } from "@/lib/domain";

async function fetchIncident(id: string): Promise<IncidentDetailType | null> {
  try {
    return await unwrap(api.GET("/api/incidents/{incident_id}", { params: { path: { incident_id: id } } }));
  } catch (err) {
    if (err instanceof ApiRequestError && err.status === 404) return null;
    throw err;
  }
}

export function IncidentDetail() {
  const { id = "" } = useParams();
  const incident = useQuery({
    queryKey: ["incidents", id],
    queryFn: () => fetchIncident(id),
    enabled: !!id,
  });

  return (
    <>
      <PageHeader
        title="Incident detail"
        description={id ? `Case ${id}` : "Missing incident id"}
        actions={
          <Link to="/incidents" className="text-sm text-slate-600 underline-offset-2 hover:underline">
            ← Back to incidents
          </Link>
        }
      />
      {!id ? (
        <p className="text-sm text-slate-500">No incident id in the URL.</p>
      ) : (
        <QueryState query={incident} isEmpty={(d) => d === null} emptyText="Incident not found.">
          {(detail) =>
            detail && (
              <div className="flex flex-col gap-4">
                <Card>
                  <CardHeader className="flex-row flex-wrap items-start justify-between gap-3">
                    <div>
                      <CardTitle className="text-base">{detail.label}</CardTitle>
                      <p className="mt-1 text-xs text-slate-500">
                        {detail.artifact_count} artifacts
                        {detail.campaign_label && (
                          <>
                            {" · "}
                            <Link to={campaignHref(detail.campaign_id)} className="text-slate-700 underline-offset-2 hover:underline">
                              {detail.campaign_label}
                            </Link>
                          </>
                        )}
                        {detail.first_seen ? ` · first seen ${new Date(detail.first_seen).toLocaleDateString()}` : ""}
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <StatusBadge status={detail.status} />
                      <OutcomeBadge outcome={detail.outcome} />
                      <CoverageBadges coverage={detail.coverage} />
                    </div>
                  </CardHeader>
                  {detail.reason_summary && (
                    <CardContent>
                      <p className="text-sm text-slate-700">{detail.reason_summary}</p>
                    </CardContent>
                  )}
                </Card>

                <DecisionCard decision={detail.decision} />
                <EvidenceList
                  evidence={detail.evidence}
                  artifactNames={Object.fromEntries(detail.artifacts.map((a) => [a.id, a.name_display]))}
                />
                <ArtifactsSection artifacts={detail.artifacts} />

                {detail.funnel.length > 0 && (
                  <Card>
                    <CardHeader>
                      <CardTitle>Funnel</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <ol className="space-y-2 text-sm">
                        {detail.funnel.map((step) => (
                          <li key={step.step} className="rounded-md border border-slate-100 px-3 py-2">
                            <span className="font-medium">Step {step.step}</span>
                            <span className="text-slate-500"> · {step.role}</span>
                            {step.domain_display && <span className="text-slate-700"> · {step.domain_display}</span>}
                            {step.redirect_chain.length > 0 && (
                              <ol className="mt-1 space-y-0.5 text-xs text-slate-500" aria-label={`Redirects in step ${step.step}`}>
                                {step.redirect_chain.map((hop) => (
                                  <li key={hop.seq} className="break-all">
                                    {hop.kind === "3xx" ? (hop.status ?? "3xx") : hop.kind} →{" "}
                                    <span className="font-mono" title={hop.url_display}>
                                      {shortUrl(hop.url_display)}
                                    </span>
                                  </li>
                                ))}
                              </ol>
                            )}
                          </li>
                        ))}
                      </ol>
                    </CardContent>
                  </Card>
                )}
              </div>
            )
          }
        </QueryState>
      )}
    </>
  );
}
