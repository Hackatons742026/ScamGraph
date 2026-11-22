import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { useSearchParams } from "react-router";
import { api, unwrap } from "@/api/client";
import type { IncidentStatus } from "@/api/types";
import { QueryState } from "@/components/domain/QueryState";
import { PageHeader } from "@/components/layout/PageHeader";
import { IncidentsTable } from "@/features/incidents/IncidentsTable";
import { STATUS } from "@/lib/domain";

const ALL_STATUSES = Object.keys(STATUS) as IncidentStatus[];

function statusesFromSearch(raw: string | null): IncidentStatus[] {
  if (!raw) return [];
  return raw
    .split(",")
    .map((s) => s.trim())
    .filter((s): s is IncidentStatus => (ALL_STATUSES as string[]).includes(s));
}

export function Incidents() {
  const [params] = useSearchParams();
  const initialStatuses = useMemo(() => statusesFromSearch(params.get("status")), [params]);

  const incidents = useQuery({
    queryKey: ["incidents"],
    queryFn: () => unwrap(api.GET("/api/incidents")),
  });

  return (
    <>
      <PageHeader title="Incidents" description="Every reported case, with coverage and status." />
      <QueryState query={incidents} isEmpty={(rows) => rows.length === 0} emptyText="No incidents yet. Run an import from Overview.">
        {(rows) => <IncidentsTable incidents={rows} initialStatuses={initialStatuses} />}
      </QueryState>
    </>
  );
}
