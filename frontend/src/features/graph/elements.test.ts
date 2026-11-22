import { describe, expect, it } from "vitest";
import type { GraphResponse } from "@/api/types";
import { FAMILY, TIER } from "@/lib/domain";
import { edgeVisual, LOW_CONFIDENCE_COLOR, stylesheet, toElements } from "./elements";

describe("edgeVisual (must match the legend)", () => {
  it("tier A is thick and solid in the tier colour", () => {
    expect(edgeVisual({ tier: "A", families: [], low_confidence: false })).toEqual({ width: 6, lineStyle: "solid", color: TIER.A.color, opacity: 1 });
  });

  it("tier B is solid, thinner than A, coloured by its family; several families use the neutral tier-B colour", () => {
    const v = edgeVisual({ tier: "B", families: ["kit"], low_confidence: false });
    expect(v).toMatchObject({ lineStyle: "solid", color: FAMILY.kit.color });
    expect(v.width).toBeLessThan(6);
    // The API sorts families alphabetically, so "first" would be arbitrary.
    expect(edgeVisual({ tier: "B", families: ["domain", "kit"], low_confidence: false }).color).toBe(TIER.B.color);
    expect(edgeVisual({ tier: "B", families: ["unknown_family"], low_confidence: false }).color).toBe(TIER.B.color);
    expect(edgeVisual({ tier: "B", families: [], low_confidence: false }).color).toBe(TIER.B.color);
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
      { id: "dangling_src", source: "gone", target: "i2", level: "network", tier: "B", families: ["kit"], score: 1, comparable: 2, low_confidence: false, evidence: [] },
    ],
  };
  const els = toElements(graph);
  const byId = (id: string) => els.find((e) => e.data.id === id);

  it("keeps known parents, drops unknown parents and dangling edges", () => {
    expect(byId("i1")!.data.parent).toBe("camp");
    expect(byId("camp")!.data.parent).toBeUndefined();
    expect(byId("dangling")).toBeUndefined();
    expect(byId("dangling_src")).toBeUndefined();
    expect(byId("e1")!.data).toMatchObject({ source: "i1", target: "i2", lineStyle: "dashed", color: LOW_CONFIDENCE_COLOR });
  });

  it("drops duplicate ids (first wins), edges reusing a node id, self-parents and parent cycles", () => {
    const node = (id: string, parent: string | null) => ({ id, kind: "campaign" as const, label: id, parent, outcome: null, coverage_level: null });
    const edge = (id: string, source: string, target: string) => ({ id, source, target, level: "network" as const, tier: "C" as const, families: [], score: 1, comparable: 2, low_confidence: false, evidence: [] });
    const out = toElements({
      nodes: [node("a", "b"), node("b", "a"), node("self", "self"), node("child", "a"), node("a", null), node("", null)],
      edges: [edge("x", "a", "b"), edge("x", "b", "a"), edge("child", "a", "b"), edge("", "a", "b"), edge("to_empty", "a", "")],
    });
    expect(out.some((e) => e.data.id === "" || e.data.id === "to_empty")).toBe(false);
    expect(out.filter((e) => e.data.id === "a")).toHaveLength(1);
    expect(out.filter((e) => e.data.id === "x")).toEqual([expect.objectContaining({ data: expect.objectContaining({ source: "a", target: "b" }) })]);
    expect(out.filter((e) => e.data.id === "child")).toHaveLength(1);
    const parent = (id: string) => out.find((e) => e.data.id === id)!.data.parent as string | undefined;
    expect([parent("a"), parent("b")].filter(Boolean)).toHaveLength(1); // the a↔b cycle is broken once, not dropped twice
    expect(parent("self")).toBeUndefined();
    expect(parent("child")).toBe("a");
  });

  it("marks low-coverage and needs-review incidents with classes", () => {
    expect(byId("i1")!.classes).toContain("low-coverage");
    expect(byId("i1")!.classes).toContain("needs-review");
    expect(byId("i2")!.classes).toBe("incident");
  });

  it("wraps graph labels and aligns compound headings inside their boundaries", () => {
    expect(stylesheet).toContainEqual(expect.objectContaining({
      selector: "node",
      style: expect.objectContaining({ "text-wrap": "wrap", "text-max-width": "92px", "text-halign": "center" }),
    }));
    expect(stylesheet).toContainEqual(expect.objectContaining({
      selector: ":parent",
      style: expect.objectContaining({ "text-wrap": "wrap", "text-halign": "left", padding: "22px" }),
    }));
  });
});
