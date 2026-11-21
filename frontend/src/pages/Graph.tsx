import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { api, unwrap } from "@/api/client";
import { QueryState } from "@/components/domain/QueryState";
import { PageHeader } from "@/components/layout/PageHeader";
import { EdgePanel } from "@/features/graph/EdgePanel";
import { EdgeTable } from "@/features/graph/EdgeTable";
import { GraphCanvas } from "@/features/graph/GraphCanvas";
import { ALL_LEVELS, ALL_TIERS, type GraphFilter } from "@/features/graph/filters";
import { GraphFilters } from "@/features/graph/GraphFilters";
import { Legend } from "@/features/graph/Legend";

export function Graph() {
  const [params] = useSearchParams();
  const campaign = params.get("campaign") ?? undefined;
  const [filter, setFilter] = useState<GraphFilter>({ tiers: ALL_TIERS, levels: ALL_LEVELS });
  const [selected, setSelected] = useState<string | null>(null);
  const navigate = useNavigate();

  const graph = useQuery({
    queryKey: ["graph", campaign ?? null, filter.tiers, filter.levels],
    queryFn: () => unwrap(api.GET("/api/graph", { params: { query: { campaign, tiers: filter.tiers.join(","), levels: filter.levels.join(",") } } })),
    placeholderData: keepPreviousData,
  });
  const selectedEdge = graph.data?.edges.find((e) => e.id === selected) ?? null;
  const noneChecked = !filter.tiers.length || !filter.levels.length;

  return (
    <>
      <PageHeader title="Investigation graph" description="Incidents grouped into campaigns and networks. Edge style shows how strong the evidence is; click a link to see why." />
      <div className="mb-3 flex flex-wrap items-center gap-4">
        <GraphFilters value={filter} onChange={(f) => { setFilter(f); setSelected(null); }} />
        {campaign && (
          <span className="text-xs text-slate-600">
            Focused on <span className="font-medium">{graph.data?.nodes.find((n) => n.id === campaign)?.label ?? "selected campaign"}</span> ·{" "}
            <Link to="/graph" className="underline">show all</Link>
          </span>
        )}
      </div>
      {noneChecked ? (
        <p className="rounded-md border border-dashed border-slate-300 p-6 text-sm text-slate-500">Select at least one tier and one level to show links.</p>
      ) : (
        <QueryState query={graph} isEmpty={(g) => g.nodes.length === 0} emptyText="No incidents to show yet. Run an import from Overview.">
          {(g) => (
            <div className="grid gap-4 xl:grid-cols-[1fr_320px]">
              <div className="flex min-w-0 flex-col gap-4">
                <GraphCanvas graph={g} selectedEdgeId={selected} onSelectEdge={setSelected} onOpenIncident={(id) => void navigate(`/incidents/${encodeURIComponent(id)}`)} />
                <EdgeTable edges={g.edges} nodes={g.nodes} selectedId={selected} onSelect={setSelected} />
              </div>
              <div className="flex flex-col gap-4">
                {selectedEdge && <EdgePanel edge={selectedEdge} nodes={g.nodes} onClose={() => setSelected(null)} />}
                <Legend />
              </div>
            </div>
          )}
        </QueryState>
      )}
    </>
  );
}
