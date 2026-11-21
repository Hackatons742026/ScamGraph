import { TIER } from "@/lib/domain";
import { ALL_LEVELS, ALL_TIERS, type GraphFilter } from "./filters";

const toggle = <T,>(list: T[], v: T) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);

export function GraphFilters({ value, onChange }: { value: GraphFilter; onChange: (f: GraphFilter) => void }) {
  return (
    <div className="flex flex-wrap items-center gap-4 text-sm">
      <fieldset className="flex items-center gap-3">
        <legend className="sr-only">Evidence tier</legend>
        <span className="text-xs font-medium text-slate-500">Tier</span>
        {ALL_TIERS.map((t) => (
          <label key={t} className="inline-flex items-center gap-1">
            <input type="checkbox" checked={value.tiers.includes(t)} onChange={() => onChange({ ...value, tiers: toggle(value.tiers, t) })} />
            {TIER[t].label}
          </label>
        ))}
      </fieldset>
      <fieldset className="flex items-center gap-3">
        <legend className="sr-only">Link level</legend>
        <span className="text-xs font-medium text-slate-500">Level</span>
        {ALL_LEVELS.map((l) => (
          <label key={l} className="inline-flex items-center gap-1 capitalize">
            <input type="checkbox" checked={value.levels.includes(l)} onChange={() => onChange({ ...value, levels: toggle(value.levels, l) })} />
            {l}
          </label>
        ))}
      </fieldset>
    </div>
  );
}
