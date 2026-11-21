import type { EdgeSingular, ElementDefinition, StylesheetJson } from "cytoscape";
import type { Edge, GraphResponse } from "@/api/types";
import { FAMILY, TIER } from "@/lib/domain";

export type EdgeVisual = { width: number; lineStyle: "solid" | "dashed"; color: string; opacity: number };

export const LOW_CONFIDENCE_COLOR = "#cbd5e1";

const familyColor = (f: string | undefined) => (f && f in FAMILY ? FAMILY[f as keyof typeof FAMILY].color : undefined);

/** Edge encoding (the legend shows exactly this): A thick solid · B solid, coloured by family · C dashed · low confidence greyed. */
export function edgeVisual(e: Pick<Edge, "tier" | "families" | "low_confidence">): EdgeVisual {
  const base: EdgeVisual =
    e.tier === "A"
      ? { width: 6, lineStyle: "solid", color: TIER.A.color, opacity: 1 }
      : e.tier === "B"
        ? { width: 3, lineStyle: "solid", color: familyColor(e.families[0]) ?? TIER.B.color, opacity: 1 }
        : { width: 2, lineStyle: "dashed", color: TIER.C.color, opacity: 1 };
  return e.low_confidence ? { ...base, color: LOW_CONFIDENCE_COLOR, opacity: 0.7 } : base;
}

/** Cytoscape elements. Parents/endpoints that are not in the response are dropped (Cytoscape would throw). */
export function toElements(graph: GraphResponse): ElementDefinition[] {
  const ids = new Set(graph.nodes.map((n) => n.id));
  const nodes: ElementDefinition[] = graph.nodes.map((n) => ({
    group: "nodes",
    data: { id: n.id, label: n.label, kind: n.kind, ...(n.parent && ids.has(n.parent) ? { parent: n.parent } : {}) },
    classes: [n.kind, n.coverage_level === "low" ? "low-coverage" : "", n.outcome === "needs_review" ? "needs-review" : ""].filter(Boolean).join(" "),
  }));
  const edges: ElementDefinition[] = graph.edges
    .filter((e) => ids.has(e.source) && ids.has(e.target))
    .map((e) => ({ group: "edges", data: { id: e.id, source: e.source, target: e.target, tier: e.tier, level: e.level, ...edgeVisual(e) } }));
  return [...nodes, ...edges];
}

export const stylesheet: StylesheetJson = [
  { selector: "node", style: { label: "data(label)", "font-size": 10, color: "#334155", "text-valign": "bottom", "text-margin-y": 4 } },
  { selector: "node.incident", style: { width: 22, height: 22, "background-color": "#475569", "border-width": 2, "border-color": "#ffffff" } },
  { selector: "node.incident.low-coverage", style: { "border-style": "dashed", "border-color": "#94a3b8", "background-color": "#94a3b8" } },
  { selector: "node.incident.needs-review", style: { "border-color": "#d97706", "border-width": 3 } },
  { selector: ":parent", style: { "text-valign": "top", "font-weight": "bold", "padding": "16px", "background-opacity": 0.06, "border-width": 1 } },
  { selector: "node.campaign", style: { "background-color": TIER.A.color, "border-color": TIER.A.color, shape: "round-rectangle" } },
  { selector: "node.network", style: { "background-color": "#1d4ed8", "border-color": "#1d4ed8", "border-style": "dashed", shape: "round-rectangle" } },
  { selector: "node.unassigned", style: { "background-color": "#64748b", "border-color": "#94a3b8", "border-style": "dotted", shape: "round-rectangle" } },
  {
    selector: "edge",
    style: {
      width: (e: EdgeSingular) => e.data("width") as number,
      "line-color": (e) => e.data("color") as string,
      "line-style": (e) => e.data("lineStyle") as EdgeVisual["lineStyle"],
      opacity: (e: EdgeSingular) => e.data("opacity") as number,
      "curve-style": "bezier",
    },
  },
  { selector: "edge:selected", style: { "underlay-color": "#0f172a", "underlay-opacity": 0.25, "underlay-padding": 4 } },
  { selector: "node:selected", style: { "overlay-color": "#0f172a", "overlay-opacity": 0.15 } },
];
