import { useQuery } from "@tanstack/react-query";
import { api, unwrap } from "@/api/client";
import { QueryState } from "@/components/domain/QueryState";
import { PageHeader } from "@/components/layout/PageHeader";
import { IncidentsTable } from "@/features/incidents/IncidentsTable";

export function Incidents() {
  const incidents = useQuery({
    queryKey: ["incidents"],
    queryFn: () => unwrap(api.GET("/api/incidents")),
  });

  return (
    <>
      <PageHeader title="Incidents" description="Every reported case, with coverage and status." />
      <QueryState query={incidents} isEmpty={(rows) => rows.length === 0} emptyText="No incidents yet. Run an import from Overview.">
        {(rows) => <IncidentsTable incidents={rows} />}
      </QueryState>
    </>
  );
}
