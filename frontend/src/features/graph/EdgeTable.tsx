import type { Edge, GraphNode } from "@/api/types";
import { TierBadge } from "@/components/domain/badges";
import { FAMILY } from "@/lib/domain";
import { cn } from "@/lib/utils";

type Props = { edges: Edge[]; nodes: GraphNode[]; selectedId: string | null; onSelect: (id: string) => void };

/** Table view of the graph's links: same selection as clicking an edge, usable without a mouse or colour vision. */
export function EdgeTable({ edges, nodes, selectedId, onSelect }: Props) {
  const label = (id: string) => nodes.find((n) => n.id === id)?.label ?? id;
  if (!edges.length) return <p className="text-sm text-slate-500">No links match the filters.</p>;
  return (
    <table className="w-full text-sm">
      <caption className="mb-1 text-left text-xs font-semibold text-slate-700">Links ({edges.length})</caption>
      <thead className="text-left text-xs text-slate-500">
        <tr><th className="py-1 pr-2 font-medium">Tier</th><th className="py-1 pr-2 font-medium">Link</th><th className="py-1 pr-2 font-medium">Level</th><th className="py-1 font-medium">Evidence</th></tr>
      </thead>
      <tbody>
        {edges.map((e) => (
          <tr key={e.id} className={cn("border-t border-slate-100", selectedId === e.id && "bg-slate-100")}>
            <td className="py-1.5 pr-2"><TierBadge tier={e.tier} /></td>
            <td className="py-1.5 pr-2">
              <button type="button" onClick={() => onSelect(e.id)} aria-pressed={selectedId === e.id} className="text-left hover:underline">
                {label(e.source)} ↔ {label(e.target)}
              </button>
            </td>
            <td className="py-1.5 pr-2 text-xs capitalize">{e.level}{e.low_confidence && <span className="ml-1 text-amber-800">(low confidence)</span>}</td>
            <td className="py-1.5 text-xs text-slate-600">
              {e.families.map((f) => FAMILY[f as keyof typeof FAMILY]?.label ?? f).join(" + ") || "—"} · {e.comparable} comparable
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
