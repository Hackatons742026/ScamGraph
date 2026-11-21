import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useId, useState } from "react";
import type { EdgeDecisionResponse } from "@/api/types";
import { Button } from "@/components/ui/button";
import { invalidateAfterOverride, postEdgeDecision } from "./api";
import { describeOverrideError } from "./errors";

type Props = { edgeId: string };

/** Confirm / reject a graph edge; shows recorded_at on success and inline errors (incl. 501). */
export function EdgeDecisionActions({ edgeId }: Props) {
  const noteId = useId();
  const client = useQueryClient();
  const [note, setNote] = useState("");
  const [recorded, setRecorded] = useState<EdgeDecisionResponse | null>(null);

  const mutation = useMutation({
    mutationFn: (decision: "confirm" | "reject") =>
      postEdgeDecision(edgeId, { decision, note: note.trim() || undefined }),
    onSuccess: (data) => {
      setRecorded(data);
      invalidateAfterOverride(client);
    },
  });

  const busy = mutation.isPending;
  const error = mutation.isError ? describeOverrideError(mutation.error) : null;

  return (
    <section aria-label="Analyst edge decision" className="flex flex-col gap-2 border-t border-slate-100 pt-3">
      <p className="text-xs font-medium text-slate-700">Analyst override</p>
      <label htmlFor={noteId} className="flex flex-col gap-1 text-xs text-slate-500">
        Note (optional)
        <textarea
          id={noteId}
          rows={2}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          disabled={busy}
          placeholder="Why confirm or reject this link…"
          className="rounded-md border border-slate-200 bg-white px-2 py-1.5 text-sm text-slate-800 placeholder:text-slate-400 disabled:opacity-60"
        />
      </label>
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          size="sm"
          disabled={busy}
          aria-busy={busy && mutation.variables === "confirm"}
          onClick={() => {
            setRecorded(null);
            mutation.mutate("confirm");
          }}
        >
          {busy && mutation.variables === "confirm" ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden /> : null}
          Confirm
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={busy}
          aria-busy={busy && mutation.variables === "reject"}
          onClick={() => {
            setRecorded(null);
            mutation.mutate("reject");
          }}
        >
          {busy && mutation.variables === "reject" ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden /> : null}
          Reject
        </Button>
      </div>
      {recorded && (
        <p role="status" className="text-xs text-slate-600">
          {recorded.decision === "confirm" ? "Confirmed" : "Rejected"} · recorded at {recorded.recorded_at}
        </p>
      )}
      {error && (
        <p role="alert" className="text-xs text-red-700">
          {error}
        </p>
      )}
    </section>
  );
}
