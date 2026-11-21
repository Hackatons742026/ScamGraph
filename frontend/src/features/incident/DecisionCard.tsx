import type { Decision } from "@/api/types";
import { OutcomeBadge } from "@/components/domain/badges";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { OUTCOME } from "@/lib/domain";
import { EvidenceChips } from "./EvidenceList";

const OUTCOME_HINT: Record<Decision["outcome"], string> = {
  known_campaign: "Linked to an existing campaign on strong evidence.",
  new_candidate: "Enough coverage to stand alone, but no campaign-level link.",
  needs_review: "Comparable evidence is thin — analyst review required.",
};

export function DecisionCard({ decision }: { decision: Decision | null }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Decision</CardTitle>
        <p className="text-xs text-slate-500">One of three routing outcomes with supporting reasons.</p>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {!decision ? (
          <p className="text-sm text-slate-500">No decision recorded for this incident yet.</p>
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <OutcomeBadge outcome={decision.outcome} />
              <span className="text-sm text-slate-600">{OUTCOME_HINT[decision.outcome]}</span>
            </div>
            {decision.campaign_label && (
              <p className="text-sm text-slate-700">
                Campaign: <span className="font-medium">{decision.campaign_label}</span>
              </p>
            )}
            <p className="text-xs text-slate-500">Decided {new Date(decision.decided_at).toLocaleString()}</p>
            <ul className="flex flex-col gap-2">
              {decision.reasons.map((reason, i) => (
                <li key={`${reason.kind}-${i}`} className="rounded-md border border-slate-100 bg-slate-50 p-3">
                  <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{reason.kind}</p>
                  <p className="mt-1 text-sm text-slate-800">{reason.text}</p>
                  <EvidenceChips evidence={reason.evidence} />
                </li>
              ))}
            </ul>
            <p className="text-xs text-slate-400">
              Outcomes: {OUTCOME.known_campaign}, {OUTCOME.new_candidate}, {OUTCOME.needs_review}.
            </p>
          </>
        )}
      </CardContent>
    </Card>
  );
}
