import type { Coverage, Family, IncidentStatus, Outcome, Tier } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { FAMILY, OUTCOME, STATUS, TIER } from "@/lib/domain";

export function TierBadge({ tier }: { tier: Tier }) {
  const t = TIER[tier];
  return (
    <span
      role="img"
      title={t.hint}
      aria-label={`${t.label}: ${t.hint}`}
      className="inline-flex h-5 min-w-5 items-center justify-center rounded px-1 text-xs font-bold text-white"
      style={{ backgroundColor: t.color }}
    >
      {tier}
    </span>
  );
}

// `Family | null`: tolerant of both the snapshot (nullable enum) and Pydantic's anyOf-null output.
export function FamilyLabel({ family }: { family: Family | null }) {
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
    // `level` is authoritative: low coverage without named gaps must never look complete.
    return coverage.level === "low" ? <Badge variant="warning">low coverage</Badge> : <Badge variant="success">full coverage</Badge>;
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

const STATUS_VARIANT = {
  in_campaign: "success",
  unassigned: "outline",
  needs_review: "warning",
  new_candidate: "default",
} as const;

export function StatusBadge({ status }: { status: IncidentStatus }) {
  return <Badge variant={STATUS_VARIANT[status]}>{STATUS[status]}</Badge>;
}
