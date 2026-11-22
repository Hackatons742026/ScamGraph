import { Link } from "react-router";
import { OutcomeBadge } from "@/components/domain/badges";
import { OUTCOME } from "@/lib/domain";
import { cn } from "@/lib/utils";
import { type LooReport, pct } from "./types";

/** Leave-one-out routing: each incident is removed, memory rebuilt, and the incident classified against the rest.
 *  Only cases that are imported incidents link to their page; synthetic evaluation cases stay plain text. */
/** `incidentLabels` is null while the incident list is unknown (loading or failed): then no case is called synthetic. */
export function LooRouting({
  loo,
  incidentLabels,
  synthetic = false,
}: {
  loo: LooReport;
  incidentLabels: ReadonlyMap<string, string> | null;
  /** When true, accuracy is from synthetic fixtures — not imported data. */
  synthetic?: boolean;
}) {
  if (!loo.rows.length) return <p className="text-sm text-slate-500">No leave-one-out routing in this report.</p>;
  const { labels, matrix } = loo.confusion;
  const correct = loo.rows.filter((r) => r.correct).length;
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-slate-700">
        Routing accuracy <span className="font-semibold tabular-nums">{pct(loo.accuracy)}</span>
        <span className="text-slate-500"> ({correct} of {loo.rows.length} incidents routed to the expected outcome)</span>
        {synthetic && (
          <span className="ml-2 rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-xs font-medium text-amber-900">
            synthetic fixtures
          </span>
        )}
      </p>
      <table className="w-fit text-sm" aria-label="Confusion matrix">
        <caption className="mb-1 text-left text-xs text-slate-500">Rows: expected outcome · columns: predicted outcome</caption>
        <thead>
          <tr>
            <th scope="col"><span className="sr-only">Expected ↓ / predicted →</span></th>
            {labels.map((l) => <th key={l} scope="col" className="px-3 py-1 text-xs font-medium text-slate-600">{OUTCOME[l]}</th>)}
          </tr>
        </thead>
        <tbody>
          {labels.map((expected, i) => (
            <tr key={expected}>
              <th scope="row" className="py-1 pr-3 text-left text-xs font-medium text-slate-600">{OUTCOME[expected]}</th>
              {labels.map((predicted, j) => (
                <td key={predicted} className={cn("px-3 py-1 text-center tabular-nums", i === j ? "bg-emerald-50 font-semibold text-emerald-800" : (matrix[i]?.[j] ?? 0) > 0 ? "bg-red-50 text-red-800" : "text-slate-400")}>
                  {matrix[i]?.[j] ?? 0}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <table className="w-full text-sm" aria-label="Leave-one-out routing per incident">
        <thead className="text-left text-xs text-slate-500">
          <tr><th className="py-1 pr-2 font-medium">Incident</th><th className="py-1 pr-2 font-medium">Expected</th><th className="py-1 pr-2 font-medium">Predicted</th><th className="py-1 font-medium">Correct</th></tr>
        </thead>
        <tbody>
          {loo.rows.map((r) => (
            <tr key={r.incident_id} className="border-t border-slate-100">
              <td className="py-1.5 pr-2">
                {incidentLabels?.has(r.incident_id)
                  ? <Link to={`/incidents/${encodeURIComponent(r.incident_id)}`} className="hover:underline">{incidentLabels.get(r.incident_id)}</Link>
                  : <span className="text-slate-600" title={incidentLabels ? "Synthetic evaluation case, not an imported incident" : undefined}>{r.incident_id}</span>}
              </td>
              <td className="py-1.5 pr-2"><OutcomeBadge outcome={r.expected} /></td>
              <td className="py-1.5 pr-2"><OutcomeBadge outcome={r.predicted} /></td>
              <td className={cn("py-1.5 text-xs font-medium", r.correct ? "text-emerald-700" : "text-red-700")}>{r.correct ? "yes" : "no"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
