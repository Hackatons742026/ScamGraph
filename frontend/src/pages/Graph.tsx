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
  const [selected, select] = useState<string | null>(null);
  // A focus change ("show all", back/forward) clears the selection: a link never follows you into another view.
  const [focus, setFocus] = useState(campaign);
  if (focus !== campaign) {
    setFocus(campaign);
    select(null);
  }
  const navigate = useNavigate();
  const noneChecked = !filter.tiers.length || !filter.levels.length;

  const graph = useQuery({
    queryKey: ["graph", campaign ?? null, filter.tiers, filter.levels],
    queryFn: () => unwrap(api.GET("/api/graph", { params: { query: { campaign, tiers: filter.tiers.join(","), levels: filter.levels.join(",") } } })),
    // An empty `tiers=` means "all" to the API: never send it.
    enabled: !noneChecked,
    placeholderData: keepPreviousData,
  });
  const data = !noneChecked && graph.isSuccess && graph.data.nodes.length > 0 ? graph.data : null;
  const selectedEdge = data?.edges.find((e) => e.id === selected) ?? null;
  const emptyText = campaign
    ? "Nothing to show for this focus: the group has no incidents at the selected levels, or it is not in the latest run. Use “show all”."
    : "No incidents to show yet. Run an import from Overview.";

  return (
    <>
      <PageHeader title="Investigation graph" description="Incidents grouped into campaigns and networks. Edge style shows how strong the evidence is; click a link to see why." />
      <div className="mb-3 flex flex-wrap items-center gap-4">
        <GraphFilters value={filter} onChange={(f) => { setFilter(f); select(null); }} />
        {campaign && (
          <span className="text-xs text-slate-600">
            Focused on <span className="font-medium">{graph.data?.nodes.find((n) => n.id === campaign)?.label ?? "selected campaign"}</span> ·{" "}
            <Link to="/graph" className="underline">show all</Link>
          </span>
        )}
      </div>
      <div className="grid gap-4 xl:grid-cols-[1fr_320px]">
        <div className="min-w-0">
          {noneChecked ? (
            <p className="rounded-md border border-dashed border-slate-300 p-6 text-sm text-slate-500">Select at least one tier and one level to show links.</p>
          ) : (
            <QueryState query={graph} isEmpty={(g) => g.nodes.length === 0} emptyText={emptyText}>
              {(g) => <GraphCanvas graph={g} selectedEdgeId={selected} onSelectEdge={select} onOpenIncident={(id) => void navigate(`/incidents/${encodeURIComponent(id)}`)} />}
            </QueryState>
          )}
        </div>
        {/* Directly after the canvas on narrow screens, sticky beside it on wide ones: a tapped link's evidence is always in view. */}
        <div className="flex flex-col gap-4 xl:sticky xl:top-4 xl:self-start">
          {data && selectedEdge && <EdgePanel edge={selectedEdge} nodes={data.nodes} onClose={() => select(null)} />}
          <Legend />
        </div>
      </div>
      {data && (
        <div className="mt-4">
          <EdgeTable edges={data.edges} nodes={data.nodes} selectedId={selected} onSelect={select} />
        </div>
      )}
    </>
  );
}
