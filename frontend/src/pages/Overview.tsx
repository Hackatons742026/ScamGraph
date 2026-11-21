import { useQuery } from "@tanstack/react-query";
import { api, unwrap } from "@/api/client";
import { QueryState } from "@/components/domain/QueryState";
import { PageHeader } from "@/components/layout/PageHeader";

export function Overview() {
  const run = useQuery({ queryKey: ["runs", "latest"], queryFn: () => unwrap(api.GET("/api/runs/latest")) });
  return (
    <>
      <PageHeader title="Overview" description="Latest analysis run: incidents → campaigns, networks and open questions." />
      <QueryState query={run}>
        {(r) => (
          <p className="text-sm text-slate-700">
            Latest run <span className="font-medium">{r.status}</span>: {r.incidents} incidents, {r.artifacts} artifacts, {r.campaigns} campaigns, {r.networks} networks, {r.needs_review} need review. Full dashboard lands in #3.
          </p>
        )}
      </QueryState>
    </>
  );
}
