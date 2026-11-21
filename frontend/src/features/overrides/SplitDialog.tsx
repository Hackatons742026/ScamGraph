import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useId, useState } from "react";
import { api, unwrap } from "@/api/client";
import type { CampaignSummary } from "@/api/types";
import { QueryState } from "@/components/domain/QueryState";
import { Button } from "@/components/ui/button";
import { invalidateAfterOverride, splitCampaign } from "./api";
import { describeOverrideError } from "./errors";
import { OverridePanel } from "./OverridePanel";

type Props = {
  campaign: CampaignSummary;
  onClose: () => void;
  onSplit?: () => void;
};

/** Split selected members out of a campaign into a new group. */
export function SplitDialog({ campaign, onClose, onSplit }: Props) {
  const noteId = useId();
  const client = useQueryClient();
  const [note, setNote] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const detail = useQuery({
    queryKey: ["campaigns", campaign.id],
    queryFn: () => unwrap(api.GET("/api/campaigns/{campaign_id}", { params: { path: { campaign_id: campaign.id } } })),
  });

  const mutation = useMutation({
    mutationFn: () =>
      splitCampaign({
        campaign_id: campaign.id,
        incident_ids: [...selected],
        note: note.trim() || undefined,
      }),
    onSuccess: () => {
      invalidateAfterOverride(client);
      onSplit?.();
      onClose();
    },
  });

  const busy = mutation.isPending;
  const error = mutation.isError ? describeOverrideError(mutation.error) : null;
  const memberCount = detail.data?.members.length ?? campaign.size;
  const canSubmit = selected.size > 0 && selected.size < memberCount;

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <OverridePanel
      title={`Split ${campaign.label}`}
      description="Move selected incidents into a new campaign. Leave at least one member in the original group."
      onClose={onClose}
      busy={busy}
    >
      <QueryState query={detail} isEmpty={(d) => d.members.length === 0} emptyText="This campaign has no members.">
        {(d) => (
          <fieldset className="flex flex-col gap-1.5" disabled={busy}>
            <legend className="text-xs font-medium text-slate-700">Members to move</legend>
            {d.members.map((m) => (
              <label key={m.id} className="flex items-center gap-2 text-sm text-slate-800">
                <input
                  type="checkbox"
                  checked={selected.has(m.id)}
                  onChange={() => toggle(m.id)}
                  className="h-4 w-4 rounded border-slate-300"
                />
                {m.label}
              </label>
            ))}
          </fieldset>
        )}
      </QueryState>

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
        <Button type="button" disabled={busy || !canSubmit || detail.isPending} aria-busy={busy} onClick={() => mutation.mutate()}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : null}
          Split
        </Button>
        <Button type="button" variant="outline" disabled={busy} onClick={onClose}>
          Cancel
        </Button>
        {selected.size > 0 && !canSubmit && (
          <span className="text-xs text-amber-800">Select a proper subset — not all members.</span>
        )}
      </div>
      {error && (
        <p role="alert" className="text-xs text-red-700">
          {error}
        </p>
      )}
    </OverridePanel>
  );
}
