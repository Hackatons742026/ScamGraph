import type { Coverage, Family, Outcome, Tier } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { FAMILY, OUTCOME, TIER } from "@/lib/domain";

export function TierBadge({ tier }: { tier: Tier }) {
  const t = TIER[tier];
  return (
    <span
      title={t.hint}
      aria-label={`${t.label}: ${t.hint}`}
      className="inline-flex h-5 min-w-5 items-center justify-center rounded px-1 text-xs font-bold text-white"
      style={{ backgroundColor: t.color }}
    >
      {tier}
    </span>
  );
}

export function FamilyLabel({ family }: { family: Family }) {
  if (!family) return null;
  const f = FAMILY[family];
  return (
    <span className="inline-flex items-center gap-1 text-xs text-slate-600">
      <span aria-hidden className="h-2 w-2 rounded-full" style={{ backgroundColor: f.color }} />
      {f.label}
    </span>
  );
}

export function CoverageBadges({ coverage }: { coverage: Coverage }) {
  if (!coverage.badges.length) {
    return <Badge variant="success">full coverage</Badge>;
  }
  return (
    <span className="inline-flex flex-wrap gap-1">
      {coverage.badges.map((b) => (
        <Badge key={b} variant={coverage.level === "low" ? "warning" : "default"}>
          {b}
        </Badge>
      ))}
    </span>
  );
}

const OUTCOME_VARIANT = { known_campaign: "danger", new_candidate: "outline", needs_review: "warning" } as const;

export function OutcomeBadge({ outcome }: { outcome: Outcome | null }) {
  if (!outcome) return <Badge>no decision</Badge>;
  return <Badge variant={OUTCOME_VARIANT[outcome]}>{OUTCOME[outcome]}</Badge>;
}
