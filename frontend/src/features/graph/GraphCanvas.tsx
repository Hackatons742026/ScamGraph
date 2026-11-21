import cytoscape, { type Core } from "cytoscape";
import fcose from "cytoscape-fcose";
import { useEffect, useRef } from "react";
import type { GraphResponse } from "@/api/types";
import { stylesheet, toElements } from "./elements";

let registered = false;

type Props = {
  graph: GraphResponse;
  selectedEdgeId: string | null;
  onSelectEdge: (id: string) => void;
  onOpenIncident: (id: string) => void;
};

/** Interactive Cytoscape view (fcose layout). The table view next to it offers the same selection without a mouse. */
export function GraphCanvas({ graph, selectedEdgeId, onSelectEdge, onOpenIncident }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const cy = useRef<Core | null>(null);
  const handlers = useRef({ onSelectEdge, onOpenIncident });

  useEffect(() => {
    handlers.current = { onSelectEdge, onOpenIncident };
  });

  useEffect(() => {
    if (!registered) {
      cytoscape.use(fcose);
      registered = true;
    }
    const instance = cytoscape({
      container: container.current,
      elements: toElements(graph),
      style: stylesheet,
      layout: { name: "fcose", animate: false, randomize: false, nodeRepulsion: 9000, idealEdgeLength: 90 } as cytoscape.LayoutOptions,
      wheelSensitivity: 0.3,
    });
    instance.on("tap", "edge", (e) => handlers.current.onSelectEdge(e.target.id()));
    instance.on("tap", "node.incident", (e) => handlers.current.onOpenIncident(e.target.id()));
    cy.current = instance;
    return () => {
      instance.destroy();
      cy.current = null;
    };
  }, [graph]);

  useEffect(() => {
    const c = cy.current;
    if (!c) return;
    c.edges().unselect();
    if (selectedEdgeId) c.getElementById(selectedEdgeId).select();
  }, [selectedEdgeId, graph]);

  return <div ref={container} data-testid="graph-canvas" aria-label="Investigation graph" role="img" className="h-[520px] w-full rounded-lg border border-slate-200 bg-white" />;
}
