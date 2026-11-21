import type { Tier } from "@/api/types";
import { FAMILY, TIER } from "@/lib/domain";
import { edgeVisual } from "./elements";

function Line({ tier, families = [], low }: { tier: Tier; families?: string[]; low?: boolean }) {
  const v = edgeVisual({ tier, families, low_confidence: !!low });
  return (
    <svg width="36" height="10" aria-hidden className="shrink-0">
      <line x1="2" y1="5" x2="34" y2="5" stroke={v.color} strokeWidth={v.width} strokeDasharray={v.lineStyle === "dashed" ? "5 4" : undefined} strokeLinecap="round" opacity={v.opacity} />
    </svg>
  );
}

/** Always visible next to the graph: how edge style maps to evidence strength. */
export function Legend() {
  return (
    <aside aria-label="Legend" className="flex flex-col gap-2 rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-700">
      <div className="font-semibold">Edges</div>
      <div className="flex items-center gap-2"><Line tier="A" /> Tier A: unique identifier (thick)</div>
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2"><Line tier="B" /> Tier B: shared infrastructure, colour = family</div>
        <div className="ml-11 flex flex-wrap gap-x-3 gap-y-1">
          {Object.entries(FAMILY).map(([k, f]) => (
            <span key={k} className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full" style={{ backgroundColor: f.color }} />{f.label}</span>
          ))}
          <span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full" style={{ backgroundColor: TIER.B.color }} />Several families</span>
        </div>
      </div>
      <div className="flex items-center gap-2"><Line tier="C" /> Tier C: weak content signal (dashed)</div>
      <div className="flex items-center gap-2"><Line tier="B" low /> Low confidence: fewer than 2 comparable types</div>
      <div className="mt-1 font-semibold">Groups</div>
      <div className="flex items-center gap-2"><span className="h-3 w-5 rounded border" style={{ borderColor: TIER.A.color }} /> Campaign</div>
      <div className="flex items-center gap-2"><span className="h-3 w-5 rounded border border-dashed border-blue-700" /> Network (shared tooling)</div>
      <div className="flex items-center gap-2"><span className="h-3 w-5 rounded border border-dotted border-slate-400" /> Unassigned</div>
      <div className="flex items-center gap-2"><span className="h-3 w-3 rounded-full border-2 border-dashed border-slate-400 bg-slate-400" /> Low-coverage incident</div>
    </aside>
  );
}
