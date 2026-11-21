import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as client from "@/api/client";
import { ApiRequestError } from "@/api/client";
import { campaigns } from "@/mocks/data";
import { renderApp } from "@/test/render";

const rows = () => within(screen.getByRole("table")).getAllByRole("row").slice(1);

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Campaigns", () => {
  it("lists campaigns and networks by size with their strongest evidence", async () => {
    renderApp("/campaigns");
    await screen.findByRole("table");
    expect(rows()).toHaveLength(campaigns.length);
    const biggest = [...campaigns].sort((a, b) => b.size - a.size)[0]!;
    expect(within(rows()[0]!).getByRole("link", { name: biggest.label })).toBeInTheDocument();
    const alpha = campaigns.find((c) => c.level === "campaign")!;
    const row = screen.getByRole("link", { name: alpha.label }).closest("tr")!;
    expect(within(row).getByText(alpha.strongest_evidence!.display)).toBeInTheDocument();
    expect(within(row).getAllByRole("cell")[2]).toHaveTextContent(new RegExp(`^${alpha.size}$`));
    expect(within(row).getByRole("img", { name: new RegExp(`^Tier ${alpha.strongest_evidence!.tier}`) })).toBeInTheDocument();
  });

  it("filters by level", async () => {
    renderApp("/campaigns");
    await screen.findByRole("table");
    await userEvent.click(screen.getByRole("button", { name: "Networks" }));
    expect(rows()).toHaveLength(campaigns.filter((c) => c.level === "network").length);
    await userEvent.click(screen.getByRole("button", { name: "Campaigns" }));
    expect(rows()).toHaveLength(campaigns.filter((c) => c.level === "campaign").length);
  });

  it("links each campaign to the graph focused on it", async () => {
    renderApp("/campaigns");
    const c = campaigns[0]!;
    expect(await screen.findByRole("link", { name: c.label })).toHaveAttribute("href", `/graph?campaign=${c.id}`);
  });

  it("shows first/last seen as dates and an em dash for missing dates or evidence", async () => {
    const full = { ...campaigns[0]!, first_seen: "2026-10-30T23:59:00Z", last_seen: "2026-11-02T00:00:00Z" };
    const bare = { ...full, id: "camp_bare", label: "Bare campaign", first_seen: null, last_seen: null, strongest_evidence: null };
    vi.spyOn(client, "unwrap").mockResolvedValueOnce([full, bare]);
    renderApp("/campaigns");
    await screen.findByRole("table");
    const cells = (label: string) => within(screen.getByRole("link", { name: label }).closest("tr")!).getAllByRole("cell").map((c) => c.textContent);
    expect(cells(full.label).slice(4)).toEqual(["2026-10-30", "2026-11-02"]);
    expect(cells("Bare campaign").slice(3)).toEqual(["—", "—", "—"]);
  });

  it("shows empty and error states", async () => {
    vi.spyOn(client, "unwrap").mockResolvedValueOnce([]);
    const { unmount } = renderApp("/campaigns");
    expect(await screen.findByText(/No campaigns yet/)).toBeInTheDocument();
    unmount();
    vi.spyOn(client, "unwrap").mockRejectedValueOnce(new ApiRequestError(500, { error: "server_error", detail: "Campaigns unavailable" }));
    renderApp("/campaigns");
    expect(await screen.findByRole("alert")).toHaveTextContent(/Campaigns unavailable/);
  });
});
