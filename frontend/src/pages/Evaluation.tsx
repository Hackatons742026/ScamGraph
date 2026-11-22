import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { api, unwrap } from "@/api/client";
import type { EvalReport } from "@/api/types";
import { QueryState } from "@/components/domain/QueryState";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AblationTable } from "@/features/eval/AblationTable";
import { LooRouting } from "@/features/eval/LooRouting";
import { PairMetrics } from "@/features/eval/PairMetrics";
import { ScenarioList } from "@/features/eval/ScenarioList";
import { hasLabelledPairs } from "@/features/eval/types";

/** The contract's "not run" shape: no timestamp, no labelled pairs and empty collections. */
const notRun = (r: EvalReport) =>
  r.generated_at === null && !hasLabelledPairs(r.pairs) && !r.scenarios.length && !r.loo.rows.length && !r.ablation.length;

function Section({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  return (
    <Card>
      <CardHeader><CardTitle>{title}</CardTitle><p className="text-xs text-slate-500">{description}</p></CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

export function Evaluation() {
  const report = useQuery({ queryKey: ["eval-report"], queryFn: () => unwrap(api.GET("/api/eval/report")) });
  // Same query as the Incidents page (shared cache): LOO rows link only to incidents that exist.
  const incidents = useQuery({ queryKey: ["incidents"], queryFn: () => unwrap(api.GET("/api/incidents")) });
  const incidentLabels = incidents.isSuccess ? new Map(incidents.data.map((i) => [i.id, i.label])) : null;
  return (
    <>
      <PageHeader title="Evaluation" description="Validation scenarios, pair metrics, leave-one-out routing and ablation. Only what was measured is shown." />
      <QueryState query={report} isEmpty={notRun} emptyText="The evaluation has not been run yet. Results appear here once it has; nothing is estimated in the meantime.">
        {(r) => (
          <div className="flex flex-col gap-4">
            {!hasLabelledPairs(r.pairs) && (
              <p role="note" className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                Not a labelled evaluation of your imported dataset. Scenarios and leave-one-out below use{" "}
                <strong>built-in synthetic fixtures</strong> — they only prove the evaluation wiring works, not DANE or live
                campaign quality. Pair metrics, false merges and ablation stay empty until you supply labelled pairs.
              </p>
            )}
            {r.generated_at !== null && <p className="text-xs text-slate-500">Generated {r.generated_at.slice(0, 16).replace("T", " ")} UTC</p>}
            <Section title="Validation scenarios" description="The seven situations the system must handle, each with its pass criterion.">
              <ScenarioList scenarios={r.scenarios} />
            </Section>
            <Section title="Pair metrics" description="Are incident pairs grouped as the labels say? Campaign and network level are scored separately.">
              <PairMetrics pairs={r.pairs} falseMerges={r.false_merges} />
            </Section>
            <Section
              title="Leave-one-out routing"
              description={
                hasLabelledPairs(r.pairs)
                  ? "Each incident is held out, memory rebuilt without it, then classified: Known Campaign, New Campaign Candidate or Needs Review."
                  : "Synthetic fixtures only — accuracy here is not performance on your imported incidents."
              }
            >
              <LooRouting loo={r.loo} incidentLabels={incidentLabels} synthetic={!hasLabelledPairs(r.pairs)} />
            </Section>
            <Section title="Ablation" description="The same evaluation with signal groups removed, showing what each contributes.">
              <AblationTable rows={r.ablation} measured={hasLabelledPairs(r.pairs)} />
            </Section>
          </div>
        )}
      </QueryState>
    </>
  );
}
