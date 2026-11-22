import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useId, useState } from "react";
import type { Edge } from "@/api/types";
import { Button } from "@/components/ui/button";
import { invalidateAfterOverride, postEdgeDecision } from "./api";
import { describeOverrideError } from "./errors";

type Props = { edge: Pick<Edge, "id" | "analyst_override"> };

/** Confirm / reject a graph edge; shows the latest persisted decision and inline errors (incl. 501). */
export function EdgeDecisionActions({ edge }: Props) {
  const noteId = useId();
  const client = useQueryClient();
  const [note, setNote] = useState("");
  const [recorded, setRecorded] = useState<{
    edgeId: string;
    value: NonNullable<Edge["analyst_override"]>;
  } | null>(null);

  const mutation = useMutation({
    mutationFn: (decision: "confirm" | "reject") =>
      postEdgeDecision(edge.id, { decision, note: note.trim() || undefined }),
    onSuccess: (data) => {
      setRecorded({
        edgeId: edge.id,
        value: { decision: data.decision, recorded_at: data.recorded_at, note: note.trim() || null },
      });
      invalidateAfterOverride(client);
    },
  });

  const busy = mutation.isPending;
  const error = mutation.isError ? describeOverrideError(mutation.error) : null;
  const latest = edge.analyst_override ?? (recorded?.edgeId === edge.id ? recorded.value : null);

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
      {latest && (
        <p role="status" className="text-xs text-slate-600">
          {latest.decision === "confirm" ? "Confirmed" : "Rejected"} · recorded at {latest.recorded_at}
          {latest.note ? ` · Note: ${latest.note}` : ""}
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
