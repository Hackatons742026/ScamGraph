import { describe, expect, it } from "vitest";
import type { GraphResponse } from "@/api/types";
import { FAMILY, TIER } from "@/lib/domain";
import { edgeVisual, LOW_CONFIDENCE_COLOR, toElements } from "./elements";

describe("edgeVisual (must match the legend)", () => {
  it("tier A is thick and solid in the tier colour", () => {
    expect(edgeVisual({ tier: "A", families: [], low_confidence: false })).toEqual({ width: 6, lineStyle: "solid", color: TIER.A.color, opacity: 1 });
  });

  it("tier B is solid, thinner than A, coloured by its first family", () => {
    const v = edgeVisual({ tier: "B", families: ["kit", "creative"], low_confidence: false });
    expect(v).toMatchObject({ lineStyle: "solid", color: FAMILY.kit.color });
    expect(v.width).toBeLessThan(6);
    expect(edgeVisual({ tier: "B", families: ["unknown_family"], low_confidence: false }).color).toBe(TIER.B.color);
  });

  it("tier C is dashed and thinnest", () => {
    const c = edgeVisual({ tier: "C", families: [], low_confidence: false });
    expect(c.lineStyle).toBe("dashed");
    expect(c.width).toBeLessThan(edgeVisual({ tier: "B", families: [], low_confidence: false }).width);
  });

  it("low confidence greys the edge but keeps its tier shape", () => {
    const v = edgeVisual({ tier: "A", families: [], low_confidence: true });
    expect(v).toMatchObject({ color: LOW_CONFIDENCE_COLOR, width: 6, lineStyle: "solid" });
    expect(v.opacity).toBeLessThan(1);
  });
});

describe("toElements", () => {
  const graph: GraphResponse = {
    nodes: [
      { id: "camp", kind: "campaign", label: "C", parent: "missing-parent", outcome: null, coverage_level: null },
      { id: "i1", kind: "incident", label: "I1", parent: "camp", outcome: "needs_review", coverage_level: "low" },
      { id: "i2", kind: "incident", label: "I2", parent: null, outcome: null, coverage_level: "ok" },
    ],
    edges: [
      { id: "e1", source: "i1", target: "i2", level: "network", tier: "C", families: [], score: 1, comparable: 1, low_confidence: true, evidence: [] },
      { id: "dangling", source: "i1", target: "gone", level: "campaign", tier: "A", families: [], score: 1, comparable: 3, low_confidence: false, evidence: [] },
    ],
  };
  const els = toElements(graph);
  const byId = (id: string) => els.find((e) => e.data.id === id);

  it("keeps known parents, drops unknown parents and dangling edges", () => {
    expect(byId("i1")!.data.parent).toBe("camp");
    expect(byId("camp")!.data.parent).toBeUndefined();
    expect(byId("dangling")).toBeUndefined();
    expect(byId("e1")!.data).toMatchObject({ source: "i1", target: "i2", lineStyle: "dashed", color: LOW_CONFIDENCE_COLOR });
  });

  it("marks low-coverage and needs-review incidents with classes", () => {
    expect(byId("i1")!.classes).toContain("low-coverage");
    expect(byId("i1")!.classes).toContain("needs-review");
    expect(byId("i2")!.classes).toBe("incident");
  });
});
