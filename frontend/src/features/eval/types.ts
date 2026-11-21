import type { EvalReport } from "@/api/types";

// Row types derived from the generated report type, so they follow the OpenAPI component names wherever they land.
export type Scenario = EvalReport["scenarios"][number];
export type PairReport = EvalReport["pairs"];
export type MetricSet = PairReport["campaign"];
export type LooReport = EvalReport["loo"];
export type AblationRow = EvalReport["ablation"][number];

/** A ratio in [0,1] as a whole percentage. */
export const pct = (x: number) => `${Math.round(x * 100)}%`;

/** Pair metrics exist only when labelled pairs were supplied; otherwise every ratio is "not measured", never 0%. */
export const hasLabelledPairs = (pairs: PairReport) => pairs.n_pairs > 0;
