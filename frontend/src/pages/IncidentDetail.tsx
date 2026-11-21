import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router";
import { api, ApiRequestError, unwrap } from "@/api/client";
import type { IncidentDetail as IncidentDetailType } from "@/api/types";
import { CoverageBadges, OutcomeBadge, StatusBadge } from "@/components/domain/badges";
import { QueryState } from "@/components/domain/QueryState";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ArtifactsSection } from "@/features/incident/ArtifactsSection";
import { DecisionCard } from "@/features/incident/DecisionCard";
import { EvidenceList } from "@/features/incident/EvidenceList";

async function fetchIncident(id: string): Promise<IncidentDetailType | null> {
  try {
    return await unwrap(api.GET("/api/incidents/{id}", { params: { path: { id } } }));
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
                        {detail.campaign_label ? ` · ${detail.campaign_label}` : ""}
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
                <EvidenceList evidence={detail.evidence} />
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
