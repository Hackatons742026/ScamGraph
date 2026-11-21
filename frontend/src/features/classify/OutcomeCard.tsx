import { Link } from "react-router";
import type { ClassifyResult, Outcome } from "@/api/types";
import { CoverageBadges, OutcomeBadge } from "@/components/domain/badges";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EvidenceChips } from "@/features/incident/EvidenceList";
import { OUTCOME } from "@/lib/domain";

const OUTCOME_HINT: Record<Outcome, string> = {
  known_campaign: "Linked to an existing campaign on strong evidence.",
  new_candidate: "Enough coverage to stand alone, but no campaign-level link.",
  needs_review: "Comparable evidence is thin — analyst review required.",
};

export function OutcomeCard({ result }: { result: ClassifyResult }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Classification outcome</CardTitle>
        <p className="text-xs text-slate-500">Known Campaign, New Campaign Candidate, or Needs Review.</p>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <OutcomeBadge outcome={result.outcome} />
          <span className="text-sm text-slate-600">{OUTCOME_HINT[result.outcome]}</span>
        </div>

        {result.campaign_label && (
          <p className="text-sm text-slate-700">
            Campaign:{" "}
            <Link
              to="/campaigns"
              className="font-medium text-slate-900 underline-offset-2 hover:underline"
            >
              {result.campaign_label}
            </Link>
            {result.campaign_id ? <span className="text-xs text-slate-500"> ({result.campaign_id})</span> : null}
          </p>
        )}

        <div className="flex flex-wrap items-center gap-2">
          <CoverageBadges coverage={result.coverage} />
          <span className="text-xs text-slate-500">{result.elapsed_ms} ms</span>
        </div>

        {result.reasons.length === 0 ? (
          <p className="text-sm text-slate-500">No reasons returned.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {result.reasons.map((reason, i) => (
              <li key={`${reason.kind}-${i}`} className="rounded-md border border-slate-100 bg-slate-50 p-3">
                <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{reason.kind}</p>
                <p className="mt-1 text-sm text-slate-800">{reason.text}</p>
                <EvidenceChips evidence={reason.evidence} />
              </li>
            ))}
          </ul>
        )}

        <p className="text-xs text-slate-400">
          Outcomes: {OUTCOME.known_campaign}, {OUTCOME.new_candidate}, {OUTCOME.needs_review}.
        </p>
      </CardContent>
    </Card>
  );
}
