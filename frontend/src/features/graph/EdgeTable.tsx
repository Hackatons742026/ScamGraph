import { Link } from "react-router";
import type { Edge, GraphNode } from "@/api/types";
import { TierBadge } from "@/components/domain/badges";
import { FAMILY } from "@/lib/domain";
import { cn } from "@/lib/utils";

type Props = { edges: Edge[]; nodes: GraphNode[]; selectedId: string | null; onSelect: (id: string | null) => void };

const incidentHref = (id: string) => `/incidents/${encodeURIComponent(id)}`;

/** Text alternative to the canvas: every link (select it to see why) and every incident, linked, including unlinked ones. */
export function EdgeTable({ edges, nodes, selectedId, onSelect }: Props) {
  const label = (id: string) => nodes.find((n) => n.id === id)?.label ?? id;
  const incident = (id: string) => <Link to={incidentHref(id)} className="hover:underline">{label(id)}</Link>;
  const linked = new Set(edges.flatMap((e) => [e.source, e.target]));
  const unlinked = nodes.filter((n) => n.kind === "incident" && !linked.has(n.id));

  return (
    <div className="flex flex-col gap-3">
      {edges.length ? (
        <table className="w-full text-sm">
          <caption className="mb-1 text-left text-xs font-semibold text-slate-700">Links ({edges.length})</caption>
          <thead className="text-left text-xs text-slate-500">
            <tr>
              <th className="py-1 pr-2 font-medium">Tier</th><th className="py-1 pr-2 font-medium">Link</th><th className="py-1 pr-2 font-medium">Level</th>
              <th className="py-1 pr-2 font-medium">Families</th><th className="py-1 font-medium"><span className="sr-only">Evidence</span></th>
            </tr>
          </thead>
          <tbody>
            {edges.map((e) => (
              <tr key={e.id} className={cn("border-t border-slate-100", selectedId === e.id && "bg-slate-100")}>
                <td className="py-1.5 pr-2"><TierBadge tier={e.tier} /></td>
                <td className="py-1.5 pr-2">{incident(e.source)} ↔ {incident(e.target)}</td>
                <td className="py-1.5 pr-2 text-xs capitalize">{e.level}{e.low_confidence && <span className="ml-1 text-amber-800">(low confidence)</span>}</td>
                <td className="py-1.5 pr-2 text-xs text-slate-600">
                  {e.families.map((f) => FAMILY[f as keyof typeof FAMILY]?.label ?? f).join(" + ") || "—"} · {e.comparable} comparable
                </td>
                <td className="py-1.5 text-right">
                  <button type="button" onClick={() => onSelect(selectedId === e.id ? null : e.id)} aria-pressed={selectedId === e.id}
                    aria-label={`Evidence for ${label(e.source)} ↔ ${label(e.target)}`} className="text-xs font-medium text-slate-700 underline-offset-2 hover:underline">
                    Evidence
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="text-sm text-slate-500">No links match the filters.</p>
      )}
      {unlinked.length > 0 && (
        <p className="text-xs text-slate-600">
          Not linked under these filters:{" "}
          {unlinked.map((n, i) => <span key={n.id}>{i > 0 && ", "}{incident(n.id)}</span>)}
        </p>
      )}
    </div>
  );
}
