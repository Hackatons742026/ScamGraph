import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Play } from "lucide-react";
import { useEffect, useState } from "react";
import { api, unwrap } from "@/api/client";
import type { RunSummary } from "@/api/types";
import { Button } from "@/components/ui/button";
import { RUN_STATUS } from "@/lib/domain";

function isActive(status: RunSummary["status"] | undefined) {
  return status === "pending" || status === "running";
}

/** Starts POST /api/import and polls GET /api/runs/{id} until the run settles. */
export function ImportRunButton() {
  const client = useQueryClient();
  const [pollKey, setPollKey] = useState(0);

  const importMutation = useMutation({
    mutationFn: () => unwrap(api.POST("/api/import", { body: {} })),
    onSuccess: () => setPollKey((k) => k + 1),
  });

  const runId = importMutation.data?.run_id ?? null;

  const activeRun = useQuery({
    queryKey: ["runs", runId, pollKey],
    queryFn: () => unwrap(api.GET("/api/runs/{id}", { params: { path: { id: runId! } } })),
    enabled: !!runId && pollKey > 0,
    refetchInterval: (q) => (isActive(q.state.data?.status) ? 400 : false),
  });

  const run = activeRun.data;
  const waitingForFirstPoll = !!runId && pollKey > 0 && !run && !activeRun.isError;
  const busy = importMutation.isPending || waitingForFirstPoll || isActive(run?.status);

  const message = importMutation.isPending
    ? "Starting import…"
    : importMutation.isError
      ? importMutation.error instanceof Error
        ? importMutation.error.message
        : "Import failed."
      : waitingForFirstPoll
        ? `Import accepted (${runId}). Waiting for run progress…`
        : isActive(run?.status)
          ? `Run ${RUN_STATUS[run!.status].toLowerCase()}…`
          : run?.status === "failed"
            ? `Run failed${run.error ? `: ${run.error}` : "."}`
            : run?.status === "done" && pollKey > 0
              ? "Import finished."
              : null;

  useEffect(() => {
    if (!run || isActive(run.status) || pollKey === 0) return;
    void client.invalidateQueries({ queryKey: ["runs", "latest"] });
    void client.invalidateQueries({ queryKey: ["incidents"] });
  }, [run, pollKey, client]);

  return (
    <div className="flex flex-col items-end gap-1">
      <Button type="button" disabled={busy} onClick={() => importMutation.mutate()} aria-busy={busy}>
        {busy ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <Play className="h-4 w-4" aria-hidden />}
        {busy ? "Importing…" : "Run import"}
      </Button>
      {message && (
        <p className="max-w-xs text-right text-xs text-slate-500" role="status" aria-live="polite">
          {message}
        </p>
      )}
    </div>
  );
}
