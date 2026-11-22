import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { api, unwrap } from "@/api/client";
import type { CampaignDetail, GraphNode, IncidentSummary } from "@/api/types";
import { CoverageBadges, StatusBadge } from "@/components/domain/badges";
import { QueryState } from "@/components/domain/QueryState";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EdgePanel } from "@/features/graph/EdgePanel";
import { EdgeTable } from "@/features/graph/EdgeTable";
import { EvidenceChips } from "@/features/incident/EvidenceList";
import { formatDate, formatTimestamp, OUTCOME } from "@/lib/domain";
import { campaignHref } from "./links";

const incidentHref = (id: string) => `/incidents/${encodeURIComponent(id)}`;

export function MembersCard({ members }: { members: IncidentSummary[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Members ({members.length})</CardTitle>
        <p className="text-xs text-slate-500">Incidents grouped here, with status and coverage.</p>
      </CardHeader>
      <CardContent>
        {members.length === 0 ? (
          <p className="text-sm text-slate-500">No member incidents.</p>
        ) : (
          <div className="overflow-x-auto">
              <table className="w-full min-w-[48rem] text-left text-sm">
              <thead className="border-b border-slate-200 text-xs text-slate-500">
                <tr>
                  <th className="py-2 pr-3 font-medium">Incident</th>
                  <th className="py-2 pr-3 font-medium">Status</th>
                  <th className="py-2 pr-3 font-medium">Coverage</th>
                  <th className="py-2 pr-3 text-right font-medium">Artifacts</th>
                  <th className="py-2 pr-3 font-medium">Source last seen</th>
                  <th className="py-2 font-medium">Ingested</th>
                </tr>
              </thead>
              <tbody>
                {members.map((m) => (
                  <tr key={m.id} className="border-b border-slate-100 last:border-0">
                    <td className="py-2 pr-3">
                      <Link to={incidentHref(m.id)} className="font-medium text-slate-900 hover:underline">{m.label}</Link>
                      {m.reason_summary && (
                        <p className="mt-0.5 line-clamp-1 text-xs text-slate-500">
                          {/* Decisions agree with membership after re-analysis; older databases may still differ. */}
                          {m.status === "in_campaign" && m.outcome && m.outcome !== "known_campaign"
                            ? `Classified as ${OUTCOME[m.outcome]} before grouping. `
                            : ""}
                          {m.reason_summary}
                        </p>
                      )}
                    </td>
                    <td className="py-2 pr-3"><StatusBadge status={m.status} /></td>
                    <td className="py-2 pr-3"><CoverageBadges coverage={m.coverage} /></td>
                    <td className="py-2 pr-3 text-right tabular-nums">{m.artifact_count}</td>
                    <td className="py-2 pr-3 tabular-nums text-slate-600">{formatTimestamp(m.last_seen)}</td>
                    <td className="py-2 tabular-nums text-slate-600">{formatTimestamp(m.ingested_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/** Links between members, with the same evidence panel (and analyst confirm/reject) as the graph. */
export function LinksCard({ campaign }: { campaign: CampaignDetail }) {
  const [selected, select] = useState<string | null>(null);
  const nodes: GraphNode[] = campaign.members.map((m) => ({
    id: m.id, kind: "incident", label: m.label, parent: null, outcome: m.outcome, coverage_level: m.coverage.level,
  }));
  const edge = campaign.edges.find((e) => e.id === selected) ?? null;
  return (
    <Card>
      <CardHeader>
        {/* The link table's caption carries the count. */}
        <CardTitle>Links between members</CardTitle>
        <p className="text-xs text-slate-500">Why members are grouped. Select a link to see its evidence.</p>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {campaign.edges.length === 0 ? (
          <p className="text-sm text-slate-500">No links between members are stored.</p>
        ) : (
          <>
            <EdgeTable edges={campaign.edges} nodes={nodes} selectedId={selected} onSelect={select} />
            {edge && <EdgePanel edge={edge} nodes={nodes} onClose={() => select(null)} />}
          </>
        )}
      </CardContent>
    </Card>
  );
}

/** Other groups this one shares evidence with (GET /api/campaigns/{id}/links). */
export function RelatedGroupsCard({ id }: { id: string }) {
  const links = useQuery({
    queryKey: ["campaigns", id, "links"],
    queryFn: () => unwrap(api.GET("/api/campaigns/{campaign_id}/links", { params: { path: { campaign_id: id } } })),
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle>Related groups</CardTitle>
        <p className="text-xs text-slate-500">Other campaigns or networks that share evidence with this one.</p>
      </CardHeader>
      <CardContent>
        <QueryState query={links} isEmpty={(rows) => rows.length === 0} emptyText="No shared evidence with other groups.">
          {(rows) => (
            <ul className="flex flex-col gap-2">
              {rows.map((link) => (
                <li key={link.other_id} className="rounded-md border border-slate-100 bg-slate-50 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Link to={campaignHref(link.other_id)} className="text-sm font-medium text-slate-900 hover:underline">{link.other_label}</Link>
                    <Badge variant={link.level === "campaign" ? "danger" : "outline"}>{link.level} link</Badge>
                  </div>
                  <EvidenceChips evidence={link.shared_evidence} />
                </li>
              ))}
            </ul>
          )}
        </QueryState>
      </CardContent>
    </Card>
  );
}

export function TimelineCard({ campaign }: { campaign: CampaignDetail }) {
  const label = (id: string) => campaign.members.find((m) => m.id === id)?.label ?? "Incident";
  const events = [...campaign.timeline].sort((a, b) => a.date.localeCompare(b.date));
  return (
    <Card>
      <CardHeader>
        <CardTitle>Timeline</CardTitle>
      </CardHeader>
      <CardContent>
        <ol className="flex flex-col gap-1.5 text-sm">
          {events.map((t, i) => (
            <li key={`${t.incident_id}-${t.date}-${i}`} className="flex flex-wrap gap-2">
              <span className="tabular-nums text-slate-500">{formatDate(t.date)}</span>
              <Link to={incidentHref(t.incident_id)} className="font-medium text-slate-900 hover:underline">{label(t.incident_id)}</Link>
              <span className="text-slate-600">{t.event}</span>
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  );
}
