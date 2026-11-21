import type { EvalReport, Outcome } from "@/api/types";
import { OUTCOME } from "@/lib/domain";

// Row types derived from the generated report type, so they follow the OpenAPI component names wherever they land.
export type Scenario = EvalReport["scenarios"][number];
export type PairReport = EvalReport["pairs"];
export type MetricSet = PairReport["campaign"];
export type LooReport = EvalReport["loo"];
export type AblationRow = EvalReport["ablation"][number];

/** A ratio in [0,1] as a whole percentage that never rounds up to a perfect 100% (or down to 0%) it didn't reach. */
export function pct(x: number): string {
  const p = Math.round(x * 100);
  if (p === 100 && x < 1) return ">99%";
  if (p === 0 && x > 0) return "<1%";
  return `${p}%`;
}

/**
 * Pair metrics, false merges and ablation are all computed from labelled pairs (backend/eval/harness.py):
 * without them nothing there was measured, so the UI says "not measured" instead of showing 0.
 */
export const hasLabelledPairs = (pairs: PairReport) => pairs.n_pairs > 0;

const OUTCOME_CODE = /\b(known_campaign|new_candidate|needs_review)\b/g;
/** Outcome codes inside report text ("expected known_campaign") as the labels the rest of the UI uses. */
export const outcomeText = (text: string) => text.replace(OUTCOME_CODE, (code) => OUTCOME[code as Outcome]);
