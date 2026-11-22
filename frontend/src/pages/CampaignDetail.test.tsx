import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { campaignDetail } from "@/mocks/data";
import * as handlers from "@/mocks/handlers";
import { renderApp } from "@/test/render";

afterEach(() => {
  vi.restoreAllMocks();
});

const card = (title: string) => screen.getByRole("heading", { name: new RegExp(`^${title}`) }).closest(".rounded-lg") as HTMLElement;

describe("Campaign detail page", () => {
  it("summarises a campaign: level, size, dates, strongest evidence, network and actions", async () => {
    const alpha = campaignDetail("camp_alpha")!;
    renderApp("/campaigns/camp_alpha");

    expect(await screen.findByRole("heading", { level: 1, name: alpha.label })).toBeInTheDocument();
    const summary = screen.getByRole("heading", { level: 3, name: alpha.label }).closest(".rounded-lg") as HTMLElement;
    expect(within(summary).getByText("campaign")).toBeInTheDocument();
    expect(summary).toHaveTextContent(`${alpha.size} incidents · first seen 2026-11-01 · last seen 2026-11-03`);
    expect(within(summary).getByText(alpha.strongest_evidence!.display)).toBeInTheDocument();
    expect(within(summary).getByRole("link", { name: /Open in graph/ })).toHaveAttribute("href", "/graph?campaign=camp_alpha");
    expect(await within(summary).findByRole("link", { name: "Synthetic shared-kit network" })).toHaveAttribute("href", "/campaigns/net_kit");
    expect(within(summary).getByRole("button", { name: `Download Evidence pack for ${alpha.label}` })).toBeInTheDocument();
    expect(within(summary).getByRole("button", { name: "Split" })).toBeInTheDocument();
  });

  it("lists members linked to their incidents and a timeline", async () => {
    const alpha = campaignDetail("camp_alpha")!;
    renderApp("/campaigns/camp_alpha");
    await screen.findByRole("heading", { level: 1, name: alpha.label });

    const members = card("Members");
    for (const m of alpha.members) {
      expect(within(members).getByRole("link", { name: m.label })).toHaveAttribute("href", `/incidents/${m.id}`);
    }
    const timeline = card("Timeline");
    expect(within(timeline).getAllByText("first seen")).toHaveLength(alpha.timeline.length);
    expect(within(timeline).getByText("2026-11-01")).toBeInTheDocument();
  });

  it("opens a member link's evidence in the shared edge panel", async () => {
    const alpha = campaignDetail("camp_alpha")!;
    const [a, b] = alpha.members;
    renderApp("/campaigns/camp_alpha");
    await screen.findByRole("heading", { level: 1, name: alpha.label });

    const links = card("Links");
    expect(links).toHaveTextContent(`Links (${alpha.edges.length})`);
    await userEvent.click(within(links).getByRole("button", { name: `Evidence for ${a!.label} ↔ ${b!.label}` }));
    const panel = within(links).getByRole("complementary", { name: "Link evidence" });
    expect(within(panel).getByRole("button", { name: "Confirm" })).toBeInTheDocument();

    await userEvent.click(within(panel).getByRole("button", { name: "Close link evidence" }));
    expect(within(links).queryByRole("complementary", { name: "Link evidence" })).not.toBeInTheDocument();
  });

  it("shows related groups from GET /api/campaigns/{id}/links", async () => {
    renderApp("/campaigns/camp_alpha");
    const related = (await screen.findByRole("heading", { name: "Related groups" })).closest(".rounded-lg") as HTMLElement;
    const other = await within(related).findByRole("link", { name: "Synthetic Campaign Beta" });
    expect(other).toHaveAttribute("href", "/campaigns/camp_beta");
    expect(within(related).getByText("network link")).toBeInTheDocument();
  });

  it("shows a network with its campaigns, without exports or split", async () => {
    renderApp("/campaigns/net_kit");
    const summary = (await screen.findByRole("heading", { level: 3, name: "Synthetic shared-kit network" })).closest(".rounded-lg") as HTMLElement;
    expect(within(summary).getByText("network")).toBeInTheDocument();
    expect(await within(summary).findByRole("link", { name: "Synthetic Campaign Alpha" })).toHaveAttribute("href", "/campaigns/camp_alpha");
    expect(within(summary).getByRole("link", { name: "Synthetic Campaign Beta" })).toHaveAttribute("href", "/campaigns/camp_beta");
    expect(within(summary).getByText(/networks are not exported/)).toBeInTheDocument();
    expect(within(summary).queryByRole("button", { name: "Split" })).not.toBeInTheDocument();
    expect(within(summary).queryByRole("button", { name: /Download/ })).not.toBeInTheDocument();
    expect(within(card("Related groups").parentElement!).queryByRole("alert")).not.toBeInTheDocument();
  });

  it("opens the split dialog from the detail page", async () => {
    renderApp("/campaigns/camp_alpha");
    await screen.findByRole("heading", { level: 1, name: "Synthetic Campaign Alpha" });
    await userEvent.click(screen.getByRole("button", { name: "Split" }));
    expect(await screen.findByRole("heading", { level: 2, name: "Split Synthetic Campaign Alpha" })).toBeInTheDocument();
  });

  it("shows a not-found state, not an error, for an unknown group", async () => {
    renderApp("/campaigns/camp_missing");
    expect(await screen.findByText(/Campaign not found/)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Campaign detail" })).toBeInTheDocument();
  });

  it("shows an error with retry when the API fails", async () => {
    const real = handlers.mockFetch;
    vi.spyOn(handlers, "mockFetch").mockImplementation(async (req: Request) =>
      new URL(req.url).pathname === "/api/campaigns/camp_alpha"
        ? Response.json({ error: "unavailable", detail: "Backend down" }, { status: 503 })
        : real(req),
    );
    renderApp("/campaigns/camp_alpha");
    expect(await screen.findByRole("alert")).toHaveTextContent(/Backend down \(503\)/);
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});
