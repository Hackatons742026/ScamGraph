import { type AblationRow, pct } from "./types";

/** Which signals matter: campaign precision/recall, false merges and routing per configuration. */
export function AblationTable({ rows, measured }: { rows: AblationRow[]; measured: boolean }) {
  if (!rows.length) return <p className="text-sm text-slate-500">No ablation results in this report.</p>;
  if (!measured) {
    return (
      <p className="rounded-md border border-dashed border-slate-300 p-4 text-sm text-slate-600">
        Ablation needs labelled pairs: each configuration&apos;s precision, recall and false merges are computed from them, so nothing is shown yet.
      </p>
    );
  }
  return (
    <div className="flex flex-col gap-2">
    <table className="w-full text-sm">
      <thead className="text-left text-xs text-slate-500">
        <tr><th className="py-1 pr-2 font-medium">Configuration</th><th className="py-1 pr-2 text-right font-medium">Campaign P</th><th className="py-1 pr-2 text-right font-medium">Campaign R</th><th className="py-1 pr-2 text-right font-medium">False merges</th><th className="py-1 text-right font-medium">LOO routing</th></tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.config} className="border-t border-slate-100 tabular-nums">
            <td className="py-1.5 pr-2 font-medium">{r.config}</td>
            <td className="py-1.5 pr-2 text-right">{pct(r.campaign_p)}</td>
            <td className="py-1.5 pr-2 text-right">{pct(r.campaign_r)}</td>
            <td className="py-1.5 pr-2 text-right">{r.false_merges}</td>
            <td className="py-1.5 text-right">{pct(r.loo_routing)}</td>
          </tr>
        ))}
      </tbody>
    </table>
    <p className="text-xs text-slate-500">LOO routing is the overall leave-one-out accuracy, repeated for each configuration (not measured per configuration).</p>
    </div>
  );
}
