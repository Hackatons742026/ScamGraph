import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { api, ApiRequestError, unwrap } from "@/api/client";
import type { RunSummary } from "@/api/types";
import { QueryState } from "@/components/domain/QueryState";
import { PageHeader } from "@/components/layout/PageHeader";
import { ImportRunButton } from "@/features/overview/ImportRunButton";
import { RunSummaryCards } from "@/features/overview/RunSummaryCards";

async function fetchLatestRun(): Promise<RunSummary | null> {
  try {
    return await unwrap(api.GET("/api/runs/latest"));
  } catch (err) {
    // 404 means no run yet — an empty state, not a hard failure.
    if (err instanceof ApiRequestError && err.status === 404) return null;
    throw err;
  }
}

export function Overview() {
  const run = useQuery({ queryKey: ["runs", "latest"], queryFn: fetchLatestRun });

  return (
    <>
      <PageHeader
        title="Overview"
        description="Latest analysis run: incidents → campaigns, networks and open questions."
        actions={<ImportRunButton />}
      />
      <QueryState query={run} isEmpty={(r) => r === null} emptyText="No analysis run yet. Start an import to process artifacts.">
        {(r) =>
          r && (
            <div className="flex flex-col gap-4">
              <RunSummaryCards run={r} />
              <p className="text-sm text-slate-600">
                Browse the{" "}
                <Link to="/incidents" className="font-medium text-slate-900 underline-offset-2 hover:underline">
                  incidents list
                </Link>{" "}
                to filter by status and coverage, or open cases that need review.
              </p>
            </div>
          )
        }
      </QueryState>
    </>
  );
}
