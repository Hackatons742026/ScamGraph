import cytoscape, { type Core } from "cytoscape";
import fcose from "cytoscape-fcose";
import { Component, type ReactNode, useEffect, useRef } from "react";
import type { GraphResponse } from "@/api/types";
import { stylesheet, toElements } from "./elements";

let registered = false;

type Props = {
  graph: GraphResponse;
  selectedEdgeId: string | null;
  onSelectEdge: (id: string) => void;
  onOpenIncident: (id: string) => void;
};

/** If Cytoscape rejects the data, keep the page (legend, link table) usable instead of crashing the app. */
class CanvasBoundary extends Component<{ resetKey: unknown; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidUpdate(prev: { resetKey: unknown }) {
    if (this.state.failed && prev.resetKey !== this.props.resetKey) this.setState({ failed: false });
  }
  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <p role="alert" className="rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
        The graph could not be drawn from this data. The link table below still lists every link.
      </p>
    );
  }
}

function CytoscapeView({ graph, selectedEdgeId, onSelectEdge, onOpenIncident }: Props) {
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
    const instance = cytoscape({ container: container.current, style: stylesheet, wheelSensitivity: 0.3 });
    try {
      instance.add(toElements(graph));
      // fcose randomizes initial positions by default; a fresh instance has none, so never pass randomize: false.
      instance.layout({ name: "fcose", animate: false, nodeRepulsion: 9000, idealEdgeLength: 90 } as cytoscape.LayoutOptions).run();
    } catch (err) {
      instance.destroy(); // the renderer is already running: do not leak it, then let CanvasBoundary show the fallback
      throw err;
    }
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

/** Interactive Cytoscape view (fcose layout). The link table offers the same selection and incident links without a mouse. */
export function GraphCanvas(props: Props) {
  return (
    <CanvasBoundary resetKey={props.graph}>
      <CytoscapeView {...props} />
    </CanvasBoundary>
  );
}
