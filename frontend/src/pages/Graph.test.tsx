import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { edges, graph } from "@/mocks/data";
import { setMockScenario } from "@/mocks/handlers";
import { renderApp } from "@/test/render";

// jsdom has no canvas: replace Cytoscape with a stub that records elements and tap handlers.
const cy = vi.hoisted(() => ({
  handlers: {} as Record<string, (e: { target: { id: () => string } }) => void>,
  lastElements: [] as unknown[],
}));
vi.mock("cytoscape", () => {
  const instance = {
    on: (ev: string, sel: string, fn: (e: { target: { id: () => string } }) => void) => { cy.handlers[`${ev} ${sel}`] = fn; },
    destroy: () => {},
    edges: () => ({ unselect: () => {} }),
    getElementById: () => ({ select: () => {} }),
  };
  const factory = (opts: { elements: unknown[] }) => { cy.lastElements = opts.elements; return instance; };
  return { default: Object.assign(factory, { use: () => {} }) };
});
vi.mock("cytoscape-fcose", () => ({ default: {} }));

// Block body: returning the handler's value would turn this into an un-awaited async act and stall later tests.
const tap = (sel: string, id: string) =>
  act(() => {
    cy.handlers[`tap ${sel}`]!({ target: { id: () => id } });
  });
const linkRows = () => within(screen.getByRole("table")).getAllByRole("row").slice(1);

describe("Investigation graph", () => {
  it("renders the canvas, an always-visible legend and a table view of every link", async () => {
    renderApp("/graph");
    expect(await screen.findByRole("img", { name: "Investigation graph" })).toBeInTheDocument();
    expect(screen.getByRole("complementary", { name: "Legend" })).toHaveTextContent(/Tier A.*Tier B.*Tier C.*Low confidence/s);
    expect(linkRows()).toHaveLength(edges.length);
    expect(cy.lastElements).toHaveLength(graph.nodes.length + edges.length);
  });

  it("opens the evidence panel from the table view, with comparability and low-confidence notes", async () => {
    renderApp("/graph");
    const weak = edges.find((e) => e.low_confidence)!;
    const row = (await screen.findAllByRole("row")).find((r) => r.textContent?.includes("low confidence"))!;
    await userEvent.click(within(row).getByRole("button"));
    const panel = screen.getByRole("complementary", { name: "Link evidence" });
    expect(panel).toHaveTextContent(`${weak.comparable} evidence types could be compared`);
    expect(panel).toHaveTextContent(/Missing data never counts as a difference/);
    expect(within(panel).getByText(weak.evidence[0]!.display)).toBeInTheDocument();
    await userEvent.click(within(panel).getByRole("button", { name: "Close link evidence" }));
    expect(screen.queryByRole("complementary", { name: "Link evidence" })).not.toBeInTheDocument();
  });

  it("explains that a shared site kit alone is a network link, and opens it from a canvas tap", async () => {
    renderApp("/graph");
    await screen.findByRole("table");
    const kit = edges.find((e) => e.level === "network" && e.families.join() === "kit")!;
    tap("edge", kit.id);
    expect(await screen.findByRole("complementary", { name: "Link evidence" })).toHaveTextContent(/shared site kit alone means shared tooling/);
  });

  it("opens an incident when its node is tapped", async () => {
    const { router } = renderApp("/graph");
    await screen.findByRole("table");
    tap("node.incident", "inc_gamma");
    await waitFor(() => expect(router.state.location.pathname).toBe("/incidents/inc_gamma"));
  });

  it("filters links by tier (server-side) and asks for a selection when nothing is checked", async () => {
    renderApp("/graph");
    await screen.findByRole("table");
    await userEvent.click(screen.getByRole("checkbox", { name: "Tier A" }));
    await waitFor(() => expect(linkRows()).toHaveLength(edges.filter((e) => e.tier !== "A").length));
    await userEvent.click(screen.getByRole("checkbox", { name: "Tier B" }));
    await userEvent.click(screen.getByRole("checkbox", { name: "Tier C" }));
    expect(screen.getByText(/Select at least one tier and one level/)).toBeInTheDocument();
  });

  it("focuses on one campaign from a deep link", async () => {
    renderApp("/graph?campaign=camp_alpha");
    expect(await screen.findByText("Campaign Alpha", { selector: "span.font-medium" })).toBeInTheDocument();
    await waitFor(() => expect(linkRows().every((r) => r.textContent?.includes("Alpha"))).toBe(true));
    expect(screen.getByRole("link", { name: "show all" })).toHaveAttribute("href", "/graph");
  });

  it("shows empty and error states", async () => {
    setMockScenario("empty");
    const { unmount } = renderApp("/graph");
    expect(await screen.findByText(/No incidents to show yet/)).toBeInTheDocument();
    unmount();
    setMockScenario("error");
    renderApp("/graph");
    expect(await screen.findByRole("alert")).toHaveTextContent(/Synthetic outage/);
  });
});
