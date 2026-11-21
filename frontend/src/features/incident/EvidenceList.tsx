import type { EvidenceItem } from "@/api/types";
import { FamilyLabel, TierBadge } from "@/components/domain/badges";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ignoreReasonLabel } from "@/lib/domain";
import { cn } from "@/lib/utils";

function EvidenceRow({ item }: { item: EvidenceItem }) {
  const ignoreLabel = item.ignored ? ignoreReasonLabel(item.ignore_reason) : null;
  return (
    <li
      className={cn(
        "flex flex-col gap-1 border-b border-slate-100 py-3 last:border-0 sm:flex-row sm:items-start sm:justify-between sm:gap-4",
        item.ignored && "opacity-60",
      )}
    >
      <div className="flex min-w-0 flex-col gap-1">
        <div className="flex flex-wrap items-center gap-2">
          <TierBadge tier={item.tier} />
          <FamilyLabel family={item.family} />
          <span className="font-mono text-sm text-slate-900">{item.display}</span>
          {item.ignored && (
            <span className="text-xs text-slate-500">Ignored{ignoreLabel ? `: ${ignoreLabel}` : ""}</span>
          )}
        </div>
        <p className="text-xs text-slate-500">
          {item.type}
          {item.detail ? ` · ${item.detail}` : ""}
        </p>
      </div>
      <div className="shrink-0 text-xs text-slate-500">
        {item.artifact_id ? (
          <span>
            Artifact <span className="font-mono text-slate-700">{item.artifact_id}</span>
            {item.funnel_step != null ? ` · funnel step ${item.funnel_step}` : ""}
          </span>
        ) : (
          <span>No source artifact</span>
        )}
      </div>
    </li>
  );
}

export function EvidenceList({ evidence }: { evidence: EvidenceItem[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Evidence</CardTitle>
        <p className="text-xs text-slate-500">Tier, family, masked display, source artifact and funnel step.</p>
      </CardHeader>
      <CardContent>
        {evidence.length === 0 ? (
          <p className="text-sm text-slate-500">No evidence linked to this incident.</p>
        ) : (
          <ul>{evidence.map((item) => <EvidenceRow key={item.id} item={item} />)}</ul>
        )}
      </CardContent>
    </Card>
  );
}

/** Compact evidence chips used inside decision reasons. */
export function EvidenceChips({ evidence }: { evidence: EvidenceItem[] }) {
  if (!evidence.length) return null;
  return (
    <ul className="mt-1 flex flex-col gap-1">
      {evidence.map((e) => (
        <li key={e.id} className={cn("flex flex-wrap items-center gap-2 text-xs", e.ignored && "opacity-60")}>
          <TierBadge tier={e.tier} />
          <FamilyLabel family={e.family} />
          <span className="font-mono">{e.display}</span>
        </li>
      ))}
    </ul>
  );
}
