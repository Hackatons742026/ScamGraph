import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { api, unwrap } from "@/api/client";
import type { Level } from "@/api/types";
import { TierBadge } from "@/components/domain/badges";
import { QueryState } from "@/components/domain/QueryState";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/badge";
import { ExportLinks } from "@/features/campaigns/ExportLinks";
import { humanize, formatDate } from "@/lib/domain";
import { cn } from "@/lib/utils";

const LEVELS: Array<{ value: Level | "all"; label: string }> = [
  { value: "all", label: "All" },
  { value: "campaign", label: "Campaigns" },
  { value: "network", label: "Networks" },
];

export function Campaigns() {
  const [level, setLevel] = useState<Level | "all">("all");
  const campaigns = useQuery({ queryKey: ["campaigns"], queryFn: () => unwrap(api.GET("/api/campaigns")) });

  return (
    <>
      <PageHeader title="Campaigns" description="Campaigns (strong shared evidence) and networks (shared tooling or infrastructure), with the strongest evidence for each." />
      <div role="group" aria-label="Filter by level" className="mb-4 flex gap-1">
        {LEVELS.map((l) => (
          <button key={l.value} type="button" aria-pressed={level === l.value} onClick={() => setLevel(l.value)}
            className={cn("h-8 rounded-full border px-3 text-xs font-medium", level === l.value ? "border-slate-900 bg-slate-900 text-white" : "border-slate-300 bg-white text-slate-700 hover:bg-slate-100")}>
            {l.label}
          </button>
        ))}
      </div>
      <QueryState query={campaigns} isEmpty={(rows) => rows.length === 0} emptyText="No campaigns yet: incidents are either unassigned or no run exists.">
        {(rows) => {
          const visible = rows.filter((c) => level === "all" || c.level === level).sort((a, b) => b.size - a.size);
          if (!visible.length) return <p className="text-sm text-slate-500">No {level}s found.</p>;
          return (
            <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
              <table className="w-full text-sm">
                <thead className="border-b border-slate-200 bg-slate-50 text-left text-xs text-slate-500">
                  <tr>
                    <th className="px-3 py-2 font-medium">Name</th><th className="px-3 py-2 font-medium">Level</th>
                    <th className="px-3 py-2 text-right font-medium">Incidents</th><th className="px-3 py-2 font-medium">Strongest evidence</th>
                    <th className="px-3 py-2 font-medium">First seen</th><th className="px-3 py-2 font-medium">Last seen</th>
                    <th className="px-3 py-2 font-medium">Export</th>
                  </tr>
                </thead>
                <tbody>
                  {visible.map((c) => (
                    <tr key={c.id} className="border-b border-slate-100 last:border-0">
                      <td className="px-3 py-2">
                        <Link to={`/graph?campaign=${encodeURIComponent(c.id)}`} className="font-medium hover:underline">{c.label}</Link>
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
    </>
  );
}
