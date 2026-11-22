import { Link } from "react-router";
import type { IncidentSummary } from "@/api/types";
import { CoverageBadges, OutcomeBadge, StatusBadge } from "@/components/domain/badges";
import { campaignHref } from "@/features/campaigns/links";

function reasonText(incident: IncidentSummary) {
  return incident.reason_summary?.trim() || "No reason summary available.";
}

export function ReviewQueue({ incidents }: { incidents: IncidentSummary[] }) {
  return (
    <ul className="flex flex-col gap-3">
      {incidents.map((incident) => (
        <li key={incident.id} className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <Link
                to={`/incidents/${incident.id}`}
                className="text-sm font-medium text-slate-900 underline-offset-2 hover:underline"
              >
                {incident.label}
              </Link>
              <p className="mt-1 text-sm text-slate-700">{reasonText(incident)}</p>
              {incident.campaign_label && (
                <p className="mt-1 text-xs text-slate-500">
                  Campaign:{" "}
                  <Link to={campaignHref(incident.campaign_id)} className="underline-offset-2 hover:underline">
                    {incident.campaign_label}
                  </Link>
                </p>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge status={incident.status} />
              {/* Status and outcome share values (needs_review, new_candidate): show the outcome only when it adds something. */}
              {incident.outcome !== incident.status && <OutcomeBadge outcome={incident.outcome} />}
              <CoverageBadges coverage={incident.coverage} />
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}
