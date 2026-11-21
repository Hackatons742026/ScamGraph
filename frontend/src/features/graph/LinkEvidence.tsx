import type { EvidenceItem } from "@/api/types";
import { FamilyLabel, TierBadge } from "@/components/domain/badges";
import { humanize, ignoreReasonLabel } from "@/lib/domain";

const TIER_ORDER = { A: 0, B: 1, C: 2 } as const;

/** Evidence behind one link, strongest first: tier, type, masked value, family, source artifact and funnel step. */
export function LinkEvidence({ evidence }: { evidence: EvidenceItem[] }) {
  if (!evidence.length) return <p className="text-sm text-slate-500">No shared evidence recorded for this link.</p>;
  const sorted = [...evidence].sort((a, b) => Number(a.ignored) - Number(b.ignored) || TIER_ORDER[a.tier] - TIER_ORDER[b.tier] || b.weight - a.weight);
  return (
    <ul aria-label="Shared evidence" className="divide-y divide-slate-100">
      {sorted.map((e) => (
        <li key={e.id} className={`flex flex-col gap-1 py-2 ${e.ignored ? "opacity-60" : ""}`}>
          <div className="flex flex-wrap items-center gap-2">
            <TierBadge tier={e.tier} />
            <span className="text-xs text-slate-500">{humanize(e.type)}</span>
            <FamilyLabel family={e.family} />
          </div>
          <code className="w-fit rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-800">{e.display}</code>
          {e.detail && <span className="text-xs text-slate-500">{e.detail}</span>}
          <span className="text-xs text-slate-500">
            from {e.artifact_id}
            {e.funnel_step !== null && ` · funnel step ${e.funnel_step}`}
          </span>
          {e.ignored && <span className="text-xs text-slate-500">Ignored: {ignoreReasonLabel(e.ignore_reason) ?? "rule"}. Never creates or strengthens a link.</span>}
        </li>
      ))}
    </ul>
  );
}
