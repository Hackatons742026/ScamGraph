import { X } from "lucide-react";
import { useEffect, useRef } from "react";
import type { Edge, GraphNode } from "@/api/types";
import { TierBadge } from "@/components/domain/badges";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EdgeDecisionActions } from "@/features/overrides/EdgeDecisionActions";
import { FAMILY } from "@/lib/domain";
import { LinkEvidence } from "./LinkEvidence";

type Props = { edge: Edge; nodes: GraphNode[]; onClose: () => void };

/** Why two incidents are linked: level, strength, comparability and the evidence list. */
export function EdgePanel({ edge, nodes, onClose }: Props) {
  const label = (id: string) => nodes.find((n) => n.id === id)?.label ?? id;
  const ref = useRef<HTMLElement>(null);
  const returnTo = useRef<HTMLElement | null>(null);

  // Opened from the table (below the fold) or the canvas: move focus here and bring it into view; remember the opener.
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const active = document.activeElement;
    if (active instanceof HTMLElement && active !== document.body && !el.contains(active)) returnTo.current = active;
    el.focus({ preventScroll: true });
    el.scrollIntoView?.({ block: "nearest" }); // optional: jsdom has no scrollIntoView
  }, [edge.id]);

  const close = () => {
    const opener = returnTo.current;
    onClose();
    opener?.focus();
  };

  return (
    <aside ref={ref} tabIndex={-1} aria-label="Link evidence" className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-4 focus:outline-none">
      <div className="flex items-start gap-2">
        <div className="flex-1">
          <div className="text-sm font-semibold">{label(edge.source)} ↔ {label(edge.target)}</div>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
            <TierBadge tier={edge.tier} />
            <Badge variant={edge.level === "campaign" ? "danger" : "outline"}>{edge.level} link</Badge>
            {edge.families.map((f) => <span key={f} className="text-slate-600">{FAMILY[f as keyof typeof FAMILY]?.label ?? f}</span>)}
          </div>
        </div>
        <Button variant="ghost" size="sm" onClick={close} aria-label="Close link evidence"><X className="h-4 w-4" aria-hidden /></Button>
      </div>
      <p className="text-xs text-slate-600">
        {edge.comparable} evidence types could be compared · score {edge.score.toFixed(1)} (evidence strength, not a fraud verdict)
      </p>
      {edge.low_confidence && <p className="text-xs text-amber-800">Low confidence: fewer than 2 evidence types are present in both incidents. Missing data never counts as a difference.</p>}
      {edge.level === "network" && edge.families.length === 1 && edge.families[0] === "kit" && (
        <p className="text-xs text-slate-600">A shared site kit alone means shared tooling: a network link only. Whether these are one campaign is left to the analyst.</p>
      )}
      <LinkEvidence evidence={edge.evidence} />
      <EdgeDecisionActions edgeId={edge.id} />
    </aside>
  );
}
