import type { UseQueryResult } from "@tanstack/react-query";
import { AlertTriangle, Inbox } from "lucide-react";
import type { ReactNode } from "react";
import { ApiRequestError } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

type Props<T> = {
  query: UseQueryResult<T>;
  children: (data: T) => ReactNode;
  isEmpty?: (data: T) => boolean;
  emptyText?: ReactNode;
};

/** Standard loading / error / empty / data rendering for every screen. */
export function QueryState<T>({ query, children, isEmpty, emptyText = "Nothing to show yet." }: Props<T>) {
  if (query.isPending) {
    return (
      <div role="status" aria-label="Loading" className="flex flex-col gap-2">
        <Skeleton className="h-6 w-1/3" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }
  if (query.isError) {
    const err = query.error;
    const detail = err instanceof ApiRequestError ? `${err.message} (${err.status})` : "Unexpected error.";
    return (
      <div role="alert" className="flex items-start gap-3 rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-800">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
        <div className="flex flex-col gap-2">
          <span>Could not load data: {detail}</span>
          <Button variant="outline" size="sm" onClick={() => void query.refetch()}>
            Retry
          </Button>
        </div>
      </div>
    );
  }
  if (isEmpty?.(query.data)) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-dashed border-slate-300 p-6 text-sm text-slate-500">
        <Inbox className="h-4 w-4" aria-hidden />
        {emptyText}
      </div>
    );
  }
  return <>{children(query.data)}</>;
}
