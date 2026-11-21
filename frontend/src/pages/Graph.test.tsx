import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as client from "@/api/client";
import { ApiRequestError } from "@/api/client";
import { edges, graph } from "@/mocks/data";
import { renderApp } from "@/test/render";

// jsdom has no canvas: replace Cytoscape with a stub that records elements, tap handlers and its lifecycle.
const cy = vi.hoisted(() => ({
  handlers: {} as Record<string, (e: { target: { id: () => string } }) => void>,
  lastElements: [] as unknown[],
  created: 0,
  destroyed: 0,
  failNext: false,
}));
vi.mock("cytoscape", () => {
  const instance = {
    on: (ev: string, sel: string, fn: (e: { target: { id: () => string } }) => void) => { cy.handlers[`${ev} ${sel}`] = fn; },
    destroy: () => { cy.destroyed += 1; },
    add: (elements: unknown[]) => {
      if (cy.failNext) {
        cy.failNext = false;
        throw new Error("Can not create edge with nonexistant source");
      }
      cy.lastElements = elements;
    },
    layout: () => ({ run: () => {} }),
    edges: () => ({ unselect: () => {} }),
    getElementById: () => ({ select: () => {} }),
  };
  const factory = () => {
    cy.created += 1;
    return instance;
  };
  return { default: Object.assign(factory, { use: () => {} }) };
});
vi.mock("cytoscape-fcose", () => ({ default: {} }));

// Block body: returning the handler's value would turn this into an un-awaited async act and stall later tests.
const tap = (sel: string, id: string) =>
  act(() => {
    cy.handlers[`tap ${sel}`]!({ target: { id: () => id } });
  });
const linkRows = () => within(screen.getByRole("table")).getAllByRole("row").slice(1);

const panel = () => screen.queryByRole("complementary", { name: "Link evidence" });
const legend = () => screen.getByRole("complementary", { name: "Legend" });
const hrefs = (el: HTMLElement) => within(el).getAllByRole("link").map((a) => a.getAttribute("href"));

beforeEach(() => {
  Object.assign(cy, { created: 0, destroyed: 0, failNext: false });
});
afterEach(() => {
  vi.restoreAllMocks();
});

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
    expect(within(panel).getByRole("button", { name: "Confirm" })).toBeInTheDocument();
    expect(within(panel).getByRole("button", { name: "Reject" })).toBeInTheDocument();
    await userEvent.click(within(panel).getByRole("button", { name: "Close link evidence" }));
    expect(screen.queryByRole("complementary", { name: "Link evidence" })).not.toBeInTheDocument();
  });

  it("records an analyst confirm from the edge panel", async () => {
    renderApp("/graph");
    await screen.findByRole("table");
    await userEvent.click(within(linkRows()[0]!).getByRole("button"));
    const panel = screen.getByRole("complementary", { name: "Link evidence" });
    await userEvent.click(within(panel).getByRole("button", { name: "Confirm" }));
    expect(await within(panel).findByRole("status")).toHaveTextContent(/Confirmed · recorded at/);
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

  it("filters links by level", async () => {
    renderApp("/graph");
    await screen.findByRole("table");
    await userEvent.click(screen.getByRole("checkbox", { name: "network" }));
    await waitFor(() => expect(linkRows()).toHaveLength(edges.filter((e) => e.level === "campaign").length));
    expect(linkRows().every((r) => r.textContent?.includes("campaign"))).toBe(true);
  });

  it("focuses on one campaign from a deep link", async () => {
    renderApp("/graph?campaign=camp_alpha");
    expect(await screen.findByText("Campaign Alpha", { selector: "span.font-medium" })).toBeInTheDocument();
    await waitFor(() => expect(linkRows().every((r) => r.textContent?.includes("Alpha"))).toBe(true));
    expect(screen.getByRole("link", { name: "show all" })).toHaveAttribute("href", "/graph");
  });

  it("creates one Cytoscape instance per graph, not per selection, and destroys it on unmount", async () => {
    const { unmount } = renderApp("/graph");
    await screen.findByRole("table");
    expect(cy.created).toBe(1);
    await userEvent.click(within(linkRows()[0]!).getByRole("button"));
    expect(panel()).toBeInTheDocument();
    expect(cy.created).toBe(1);
    unmount();
    expect(cy.destroyed).toBe(1);
  });

  it("keeps the legend visible while loading, on error and with nothing checked", async () => {
    vi.spyOn(client, "unwrap").mockRejectedValueOnce(new ApiRequestError(500, { error: "server_error", detail: "Graph unavailable" }));
    renderApp("/graph");
    expect(screen.getByRole("status", { name: "Loading" })).toBeInTheDocument();
    expect(legend()).toBeInTheDocument();
    await screen.findByRole("alert");
    expect(legend()).toBeInTheDocument();
    await userEvent.click(screen.getByRole("checkbox", { name: "campaign" }));
    await userEvent.click(screen.getByRole("checkbox", { name: "network" }));
    expect(screen.getByText(/Select at least one tier and one level/)).toBeInTheDocument();
    expect(legend()).toBeInTheDocument();
  });

  it("keeps the link table usable when Cytoscape rejects the data, without leaking, and draws again on the next graph", async () => {
    // React reports the caught error via console.error and (in dev) a window "error" event that jsdom prints.
    vi.spyOn(console, "error").mockImplementation(() => {});
    const silence = (e: ErrorEvent) => e.preventDefault();
    window.addEventListener("error", silence);
    cy.failNext = true;
    renderApp("/graph");
    expect(await screen.findByRole("alert")).toHaveTextContent(/could not be drawn/);
    expect(linkRows()).toHaveLength(edges.length);
    expect(cy.destroyed).toBe(1);
    await userEvent.click(screen.getByRole("checkbox", { name: "Tier C" }));
    expect(await screen.findByRole("img", { name: "Investigation graph" })).toBeInTheDocument();
    expect(screen.queryByText(/could not be drawn/)).not.toBeInTheDocument();
    expect(cy.created).toBe(2);
    window.removeEventListener("error", silence);
  });

  it("moves focus to the evidence panel and back to its opener; the Evidence button toggles", async () => {
    renderApp("/graph");
    await screen.findByRole("table");
    const button = within(linkRows()[0]!).getByRole("button");
    await userEvent.click(button);
    expect(panel()).toHaveFocus();
    await userEvent.click(within(panel()!).getByRole("button", { name: "Close link evidence" }));
    expect(panel()).not.toBeInTheDocument();
    expect(button).toHaveFocus();
    await userEvent.click(button);
    expect(button).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(button);
    expect(panel()).not.toBeInTheDocument();
    expect(button).toHaveAttribute("aria-pressed", "false");
  });

  it("links every incident from the table view, including incidents without links", async () => {
    renderApp("/graph");
    await screen.findByRole("table");
    expect(hrefs(linkRows()[0]!)).toEqual([`/incidents/${edges[0]!.source}`, `/incidents/${edges[0]!.target}`]);
    const linked = new Set(edges.flatMap((e) => [e.source, e.target]));
    const unlinked = graph.nodes.filter((n) => n.kind === "incident" && !linked.has(n.id));
    expect(unlinked.length).toBeGreaterThan(0);
    expect(hrefs(screen.getByText(/Not linked under these filters/))).toEqual(unlinked.map((n) => `/incidents/${n.id}`));
  });

  it("clears the selected link when the focus changes, in both directions", async () => {
    const { router } = renderApp("/graph?campaign=camp_alpha");
    await screen.findByRole("table");
    await userEvent.click(screen.getByRole("link", { name: "show all" }));
    await waitFor(() => expect(linkRows()).toHaveLength(edges.length));
    // A link that also exists in the focused view: without the reset its panel would follow us back.
    await userEvent.click(within(linkRows().find((r) => r.textContent?.includes("Alpha-1"))!).getByRole("button"));
    expect(panel()).toBeInTheDocument();
    await act(() => router.navigate(-1));
    await waitFor(() => expect(linkRows()).toHaveLength(1));
    expect(panel()).not.toBeInTheDocument();
    await userEvent.click(within(linkRows()[0]!).getByRole("button"));
    expect(panel()).toBeInTheDocument();
    await userEvent.click(screen.getByRole("link", { name: "show all" }));
    await waitFor(() => expect(linkRows()).toHaveLength(edges.length));
    expect(panel()).not.toBeInTheDocument();
  });

  it("explains an empty focused view instead of asking for an import", async () => {
    renderApp("/graph?campaign=camp_not_in_run");
    expect(await screen.findByText(/Nothing to show for this focus/)).toBeInTheDocument();
    expect(screen.queryByText(/Run an import/)).not.toBeInTheDocument();
  });

  it("shows empty and error states", async () => {
    vi.spyOn(client, "unwrap").mockResolvedValueOnce({ nodes: [], edges: [] });
    const { unmount } = renderApp("/graph");
    expect(await screen.findByText(/No incidents to show yet/)).toBeInTheDocument();
    unmount();
    vi.spyOn(client, "unwrap").mockRejectedValueOnce(new ApiRequestError(500, { error: "server_error", detail: "Graph unavailable" }));
    renderApp("/graph");
    expect(await screen.findByRole("alert")).toHaveTextContent(/Graph unavailable/);
  });
});
