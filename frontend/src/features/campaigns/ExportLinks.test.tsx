import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "@/api/client";
import { campaignDetail, campaigns } from "@/mocks/data";
import { renderApp } from "@/test/render";

// jsdom can't save files: record what would be downloaded, and under which name.
const saved = { blobs: [] as Blob[], names: [] as string[] };
beforeEach(() => {
  saved.blobs = [];
  saved.names = [];
  vi.spyOn(URL, "createObjectURL").mockImplementation((b) => (saved.blobs.push(b as Blob), "blob:synthetic"));
  vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
    saved.names.push(this.download);
  });
});
afterEach(() => {
  vi.restoreAllMocks();
});

const campaign = campaigns.find((c) => c.level === "campaign")!;
const network = campaigns.find((c) => c.level === "network")!;
const row = (label: string) => screen.getByRole("link", { name: label }).closest("tr")!;
const failWith = (status: number, error: unknown) => {
  const real = api.GET.bind(api);
  vi.spyOn(api, "GET").mockImplementation(((path: string, init: unknown) =>
    path === "/api/exports/{name}" ? Promise.resolve({ error, response: new Response(null, { status }) }) : real(path as never, init as never)) as never);
};

describe("Campaign exports", () => {
  it("offers evidence pack, CSV and MISP per campaign and saves the masked file under the server's name", async () => {
    renderApp("/campaigns");
    await screen.findByRole("table");
    for (const label of ["Evidence pack", "CSV", "MISP"]) {
      expect(within(row(campaign.label)).getByRole("button", { name: `Download ${label} for ${campaign.label}` })).toBeInTheDocument();
    }
    const csv = within(row(campaign.label)).getByRole("button", { name: `Download CSV for ${campaign.label}` });
    await userEvent.click(csv);
    await waitFor(() => expect(saved.names).toHaveLength(1));
    expect(saved.names[0]).toMatch(/^scamgraph-campaign-[0-9a-f]{16}\.csv$/);
    const text = await saved.blobs[0]!.text();
    expect(text).toMatch(/^record_type,campaign_ref,incident_ref\n/);
    for (const id of [campaign.id, ...campaignDetail(campaign.id)!.members.map((m) => m.id)]) expect(text).not.toContain(id);
  });

  it("keeps buttons focusable while a download is in flight (aria-disabled, never disabled) and marks the busy one", async () => {
    let finish!: () => void;
    const real = api.GET.bind(api);
    vi.spyOn(api, "GET").mockImplementation(((path: string, init: unknown) =>
      path === "/api/exports/{name}"
        ? new Promise((resolve) => { finish = () => resolve({ data: new Blob(["x"]), error: undefined, response: new Response("x") }); })
        : real(path as never, init as never)) as never);
    renderApp("/campaigns");
    await screen.findByRole("table");
    const buttons = within(row(campaign.label)).getAllByRole("button");
    const csv = within(row(campaign.label)).getByRole("button", { name: `Download CSV for ${campaign.label}` });
    await userEvent.click(csv);
    await waitFor(() => expect(csv).toHaveAttribute("aria-busy", "true"));
    for (const b of buttons) {
      expect(b).toHaveAttribute("aria-disabled", "true");
      expect(b).not.toBeDisabled();
    }
    finish();
    await waitFor(() => expect(csv).toHaveAttribute("aria-busy", "false"));
    expect(csv).toHaveAttribute("aria-disabled", "false");
  });

  it("offers no exports for networks (the backend exports campaigns only)", async () => {
    renderApp("/campaigns");
    await screen.findByRole("table");
    expect(within(row(network.label)).queryByRole("button")).not.toBeInTheDocument();
    expect(within(row(network.label)).getByTitle(/networks are not exported/)).toHaveTextContent("—");
  });

  it("shows a failed export inline instead of downloading an error page", async () => {
    failWith(501, { error: "http_error", detail: "Exports require a configured live database" });
    renderApp("/campaigns");
    await screen.findByRole("table");
    await userEvent.click(within(row(campaign.label)).getByRole("button", { name: `Download MISP for ${campaign.label}` }));
    expect(await within(row(campaign.label)).findByRole("alert")).toHaveTextContent("Export failed: Exports require a configured live database (501)");
    expect(saved.names).toEqual([]);
  });

  it("does not repeat the status when the error has no detail", async () => {
    failWith(502, undefined);
    renderApp("/campaigns");
    await screen.findByRole("table");
    await userEvent.click(within(row(campaign.label)).getByRole("button", { name: `Download CSV for ${campaign.label}` }));
    const alert = await within(row(campaign.label)).findByRole("alert");
    expect(alert).toHaveTextContent("Export failed: Request failed with status 502");
    expect(alert).not.toHaveTextContent("(502)");
  });
});
