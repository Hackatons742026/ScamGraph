import { type MetricSet, type PairReport, hasLabelledPairs, pct } from "./types";

function MetricCard({ title, m }: { title: string; m: MetricSet }) {
  return (
    <div className="rounded-md border border-slate-200 p-3">
      <div className="text-xs font-semibold text-slate-700">{title}</div>
      <dl className="mt-2 grid grid-cols-3 gap-2 text-center">
        {([["Precision", m.precision], ["Recall", m.recall], ["F1", m.f1]] as const).map(([label, v]) => (
          <div key={label}><dt className="text-xs text-slate-500">{label}</dt><dd className="text-lg font-semibold tabular-nums">{pct(v)}</dd></div>
        ))}
      </dl>
      <p className="mt-2 text-xs text-slate-500 tabular-nums">TP {m.tp} · FP {m.fp} · FN {m.fn}</p>
    </div>
  );
}

/** Pair precision/recall/F1 at campaign and network level, plus false merges and mentor agreement. */
export function PairMetrics({ pairs, falseMerges }: { pairs: PairReport; falseMerges: number }) {
  return (
    <div className="flex flex-col gap-3">
      <p className={`text-sm font-medium ${falseMerges === 0 ? "text-emerald-700" : "text-red-700"}`}>
        False merges: <span className="tabular-nums">{falseMerges}</span>
        <span className="font-normal text-slate-500"> · separate campaigns wrongly joined into one</span>
      </p>
      {hasLabelledPairs(pairs) ? (
        <>
          <div className="grid gap-3 md:grid-cols-2">
            <MetricCard title="Campaign level" m={pairs.campaign} />
            <MetricCard title="Network level" m={pairs.network} />
          </div>
          <p className="text-xs text-slate-500">
            {pairs.n_pairs} labelled pairs · {pairs.mentor_verified} mentor-verified
            {pairs.agreement !== null && ` · mentor agreement ${pct(pairs.agreement)}`}
          </p>
        </>
      ) : (
        <p className="rounded-md border border-dashed border-slate-300 p-4 text-sm text-slate-600">
          No labelled pairs in this report, so precision, recall and F1 are not measured. Supply a local label CSV to compute them.
        </p>
      )}
    </div>
  );
}
