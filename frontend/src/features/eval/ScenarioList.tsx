import { CheckCircle2, XCircle } from "lucide-react";
import { outcomeText, type Scenario } from "./types";

/** The seven validation scenarios with pass/fail and the reason. */
export function ScenarioList({ scenarios }: { scenarios: Scenario[] }) {
  if (!scenarios.length) return <p className="text-sm text-slate-500">No scenario results in this report.</p>;
  const passed = scenarios.filter((s) => s.passed).length;
  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm text-slate-700"><span className="font-semibold">{passed} of {scenarios.length}</span> scenarios pass.</p>
      <table className="w-full text-sm">
        <thead className="text-left text-xs text-slate-500">
          <tr><th className="py-1 pr-2 font-medium">#</th><th className="py-1 pr-2 font-medium">Scenario</th><th className="py-1 pr-2 font-medium">Criterion</th><th className="py-1 pr-2 font-medium">Result</th><th className="py-1 font-medium">Details</th></tr>
        </thead>
        <tbody>
          {[...scenarios].sort((a, b) => a.id - b.id).map((s) => (
            <tr key={s.id} className="border-t border-slate-100 align-top">
              <td className="py-1.5 pr-2 tabular-nums text-slate-500">{s.id}</td>
              <td className="py-1.5 pr-2 font-medium">{s.name}</td>
              <td className="py-1.5 pr-2 text-xs text-slate-600">{outcomeText(s.criterion)}</td>
              <td className="py-1.5 pr-2">
                {s.passed
                  ? <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-700"><CheckCircle2 className="h-4 w-4" aria-hidden />Pass</span>
                  : <span className="inline-flex items-center gap-1 text-xs font-medium text-red-700"><XCircle className="h-4 w-4" aria-hidden />Fail</span>}
              </td>
              <td className="py-1.5 text-xs text-slate-600">{outcomeText(s.details)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
