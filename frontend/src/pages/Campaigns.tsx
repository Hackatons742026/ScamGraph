import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router";
import { api, unwrap } from "@/api/client";
import type { CampaignSummary, Level } from "@/api/types";
import { TierBadge } from "@/components/domain/badges";
import { QueryState } from "@/components/domain/QueryState";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ExportLinks } from "@/features/campaigns/ExportLinks";
import { campaignHref, graphFocusHref } from "@/features/campaigns/links";
import { MergeDialog } from "@/features/overrides/MergeDialog";
import { SplitDialog } from "@/features/overrides/SplitDialog";
import { humanize, formatDate } from "@/lib/domain";
import { cn } from "@/lib/utils";

const LEVELS: Array<{ value: Level | "all"; label: string }> = [
  { value: "all", label: "All" },
  { value: "campaign", label: "Campaigns" },
  { value: "network", label: "Networks" },
];

function campaignIdsVisible(rows: CampaignSummary[], level: Level | "all"): Set<string> {
  return new Set(
    rows.filter((c) => c.level === "campaign" && (level === "all" || c.level === level)).map((c) => c.id),
  );
}

export function Campaigns() {
  const [level, setLevel] = useState<Level | "all">("all");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [mergeOpen, setMergeOpen] = useState(false);
  const [splitTarget, setSplitTarget] = useState<CampaignSummary | null>(null);
  const campaigns = useQuery({ queryKey: ["campaigns"], queryFn: () => unwrap(api.GET("/api/campaigns")) });

  const visible = useMemo(() => {
    const rows = campaigns.data ?? [];
    return rows.filter((c) => level === "all" || c.level === level).sort((a, b) => b.size - a.size);
  }, [campaigns.data, level]);

  // Selection is only campaign-level rows that are still visible under the current filter.
  const selectedCampaigns = useMemo(
    () => visible.filter((c) => c.level === "campaign" && selected.has(c.id)),
    [visible, selected],
  );

  const setFilter = (next: Level | "all") => {
    setLevel(next);
    const keep = campaignIdsVisible(campaigns.data ?? [], next);
    setSelected((prev) => new Set([...prev].filter((id) => keep.has(id))));
  };

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <>
      <PageHeader title="Campaigns" description="Campaigns (strong shared evidence) and networks (shared tooling or infrastructure), with the strongest evidence for each. Open a name for its members, links and timeline." />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div role="group" aria-label="Filter by level" className="flex gap-1">
          {LEVELS.map((l) => (
            <button key={l.value} type="button" aria-pressed={level === l.value} onClick={() => setFilter(l.value)}
              className={cn("h-8 rounded-full border px-3 text-xs font-medium", level === l.value ? "border-slate-900 bg-slate-900 text-white" : "border-slate-300 bg-white text-slate-700 hover:bg-slate-100")}>
              {l.label}
            </button>
          ))}
        </div>
        <Button
          type="button"
          size="sm"
          disabled={selectedCampaigns.length < 2}
          onClick={() => setMergeOpen(true)}
          title={selectedCampaigns.length < 2 ? "Select at least two campaigns to merge" : "Merge selected campaigns"}
        >
          Merge selected{selectedCampaigns.length >= 2 ? ` (${selectedCampaigns.length})` : ""}
        </Button>
      </div>
      <QueryState query={campaigns} isEmpty={(rows) => rows.length === 0} emptyText="No campaigns yet: incidents are either unassigned or no run exists.">
        {() => {
          if (!visible.length) return <p className="text-sm text-slate-500">No {level}s found.</p>;
          return (
            <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
              <table className="w-full text-sm">
                <thead className="border-b border-slate-200 bg-slate-50 text-left text-xs text-slate-500">
                  <tr>
                    <th className="px-3 py-2 font-medium"><span className="sr-only">Select</span></th>
                    <th className="px-3 py-2 font-medium">Name</th><th className="px-3 py-2 font-medium">Level</th>
                    <th className="px-3 py-2 text-right font-medium">Incidents</th><th className="px-3 py-2 font-medium">Strongest evidence</th>
                    <th className="px-3 py-2 font-medium">First seen</th><th className="px-3 py-2 font-medium">Last seen</th>
                    <th className="px-3 py-2 font-medium">Actions</th>
                    <th className="px-3 py-2 font-medium">Export</th>
                  </tr>
                </thead>
                <tbody>
                  {visible.map((c) => (
                    <tr key={c.id} className="border-b border-slate-100 last:border-0">
                      <td className="px-3 py-2">
                        {c.level === "campaign" ? (
                          <input
                            type="checkbox"
                            checked={selected.has(c.id)}
                            onChange={() => toggle(c.id)}
                            aria-label={`Select ${c.label}`}
                            className="h-4 w-4 rounded border-slate-300"
                          />
                        ) : (
                          <span className="sr-only">Networks cannot be merged</span>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        <Link to={campaignHref(c.id)} className="font-medium hover:underline">{c.label}</Link>
                        {c.network_id && <div className="text-xs text-slate-500">part of a wider network</div>}
                      </td>
                      <td className="px-3 py-2"><Badge variant={c.level === "campaign" ? "danger" : "outline"}>{c.level}</Badge></td>
                      <td className="px-3 py-2 text-right tabular-nums">{c.size}</td>
                      <td className="px-3 py-2">
                        {c.strongest_evidence ? (
                          <span className="inline-flex items-center gap-2">
                            <TierBadge tier={c.strongest_evidence.tier} />
                            <span className="text-xs text-slate-500">{humanize(c.strongest_evidence.type)}</span>
                            <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs">{c.strongest_evidence.display}</code>
                          </span>
                        ) : "—"}
                      </td>
                      <td className="px-3 py-2 tabular-nums">{formatDate(c.first_seen)}</td>
                      <td className="px-3 py-2 tabular-nums">{formatDate(c.last_seen)}</td>
                      <td className="px-3 py-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <Link to={graphFocusHref(c.id)} aria-label={`Open ${c.label} in the graph`} className="text-xs font-medium text-slate-700 underline-offset-2 hover:underline">
                            Graph
                          </Link>
                          {c.level === "campaign" && c.size >= 2 && (
                            <Button type="button" size="sm" variant="outline" onClick={() => setSplitTarget(c)}>
                              Split
                            </Button>
                          )}
                        </div>
                      </td>
                      <td className="px-3 py-2">
                        {c.level === "campaign" ? <ExportLinks campaignId={c.id} label={c.label} /> : <span className="text-xs text-slate-400" title="Exports are per campaign; networks are not exported">—</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }}
      </QueryState>

      {mergeOpen && selectedCampaigns.length >= 2 && (
        <MergeDialog
          campaigns={selectedCampaigns}
          onClose={() => setMergeOpen(false)}
          onMerged={() => setSelected(new Set())}
        />
      )}
      {splitTarget && <SplitDialog campaign={splitTarget} onClose={() => setSplitTarget(null)} />}
    </>
  );
}
