import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { api, unwrap } from "@/api/client";
import { QueryState } from "@/components/domain/QueryState";
import { PageHeader } from "@/components/layout/PageHeader";
import { ReviewQueue } from "@/features/review/ReviewQueue";

const REVIEW_STATUSES = "needs_review,unassigned";

export function Review() {
  const queue = useQuery({
    queryKey: ["incidents", "review", REVIEW_STATUSES],
    queryFn: () =>
      unwrap(
        api.GET("/api/incidents", {
          params: { query: { status: REVIEW_STATUSES } },
        }),
      ),
  });

  const newCandidates = useQuery({
    queryKey: ["incidents", "new_candidate"],
    queryFn: () =>
      unwrap(
        api.GET("/api/incidents", {
          params: { query: { status: "new_candidate" } },
        }),
      ),
    enabled: queue.isSuccess && (queue.data?.length ?? 0) === 0,
  });

  const emptyText = (
    <span className="flex flex-col gap-2">
      <span>No incidents need review right now (Needs Review / Unassigned only).</span>
      {(newCandidates.data?.length ?? 0) > 0 && (
        <span>
          {newCandidates.data!.length} New Candidate
          {newCandidates.data!.length === 1 ? "" : "s"} sit outside campaigns —{" "}
          <Link
            to="/incidents?status=new_candidate"
            className="font-medium text-slate-800 underline underline-offset-2 hover:text-slate-950"
          >
            open New Candidates in Incidents
          </Link>
          .
        </span>
      )}
    </span>
  );

  return (
    <>
      <PageHeader
        title="Review queue"
        description="Needs Review and Unassigned only. New Candidates are listed under Incidents."
      />
      <QueryState query={queue} isEmpty={(rows) => rows.length === 0} emptyText={emptyText}>
        {(rows) => <ReviewQueue incidents={rows} />}
      </QueryState>
    </>
  );
}
