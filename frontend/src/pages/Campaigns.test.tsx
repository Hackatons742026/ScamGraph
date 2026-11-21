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
