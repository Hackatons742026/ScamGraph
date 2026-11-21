import { useQuery } from "@tanstack/react-query";
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

  return (
    <>
      <PageHeader title="Review queue" description="Unassigned and Needs Review incidents." />
      <QueryState
        query={queue}
        isEmpty={(rows) => rows.length === 0}
        emptyText="No incidents need review right now."
      >
        {(rows) => <ReviewQueue incidents={rows} />}
      </QueryState>
    </>
  );
}
