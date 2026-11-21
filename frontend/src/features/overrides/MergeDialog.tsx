import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useId, useState } from "react";
import type { CampaignSummary } from "@/api/types";
import { Button } from "@/components/ui/button";
import { invalidateAfterOverride, mergeCampaigns } from "./api";
import { describeOverrideError } from "./errors";
import { OverridePanel } from "./OverridePanel";

type Props = {
  campaigns: CampaignSummary[];
  onClose: () => void;
  onMerged?: () => void;
};

/** Merge two or more selected campaigns into one. */
export function MergeDialog({ campaigns, onClose, onMerged }: Props) {
  const noteId = useId();
  const client = useQueryClient();
  const [note, setNote] = useState("");

  const mutation = useMutation({
    mutationFn: () => mergeCampaigns({ campaign_ids: campaigns.map((c) => c.id), note: note.trim() || undefined }),
    onSuccess: () => {
      invalidateAfterOverride(client);
      onMerged?.();
      onClose();
    },
  });

  const busy = mutation.isPending;
  const error = mutation.isError ? describeOverrideError(mutation.error) : null;

  return (
    <OverridePanel
      title="Merge campaigns"
      description={`Combine ${campaigns.length} selected groups into one campaign. This is an analyst override, not an automatic engine decision.`}
      onClose={onClose}
      busy={busy}
    >
      <ul className="list-inside list-disc text-xs text-slate-700">
        {campaigns.map((c) => (
          <li key={c.id}>
            {c.label} <span className="text-slate-500">({c.size} incidents)</span>
          </li>
        ))}
      </ul>
      <label htmlFor={noteId} className="flex flex-col gap-1 text-xs text-slate-500">
        Note (optional)
        <textarea
          id={noteId}
          rows={2}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          disabled={busy}
          className="rounded-md border border-slate-200 bg-white px-2 py-1.5 text-sm text-slate-800 disabled:opacity-60"
        />
      </label>
      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" disabled={busy || campaigns.length < 2} aria-busy={busy} onClick={() => mutation.mutate()}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : null}
          Merge
        </Button>
        <Button type="button" variant="outline" disabled={busy} onClick={onClose}>
          Cancel
        </Button>
      </div>
      {error && (
        <p role="alert" className="text-xs text-red-700">
          {error}
        </p>
      )}
    </OverridePanel>
  );
}
