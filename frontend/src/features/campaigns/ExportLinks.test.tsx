import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "@/api/client";
import { campaignDetail, campaigns } from "@/mocks/data";
import { renderApp } from "@/test/render";

// jsdom has no object URLs: record what would be downloaded, and under which filename.
const saved = vi.hoisted(() => ({ blobs: [] as Blob[], names: [] as string[] }));
beforeEach(() => {
  saved.blobs = [];
  saved.names = [];
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: (b: Blob) => (saved.blobs.push(b), "blob:synthetic"), revokeObjectURL: () => {} }));
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
    saved.names.push(this.download);
  });
});
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

const row = (label: string) => screen.getByRole("link", { name: label }).closest("tr")!;

describe("Campaign exports", () => {
  it("offers evidence pack, CSV and MISP per campaign and saves the file under the server's name", async () => {
    renderApp("/campaigns");
    await screen.findByRole("table");
    const c = campaigns[0]!;
    for (const label of ["Evidence pack", "CSV", "MISP"]) {
      expect(within(row(c.label)).getByRole("button", { name: `Download ${label} for ${c.label}` })).toBeInTheDocument();
    }
    await userEvent.click(within(row(c.label)).getByRole("button", { name: `Download CSV for ${c.label}` }));
    await waitFor(() => expect(saved.names).toEqual([`scamgraph-${c.id}.csv`]));
    const text = await saved.blobs[0]!.text();
    for (const member of campaignDetail(c.id)!.members) expect(text).toContain(member.id);
  });

  it("shows a failed export inline instead of downloading an error page", async () => {
    const real = api.GET.bind(api);
    vi.spyOn(api, "GET").mockImplementation(((path: string, init: unknown) =>
      path === "/api/exports/{name}"
        ? Promise.resolve({ error: { error: "http_error", detail: "Exports require a configured live database" }, response: new Response(null, { status: 501 }) })
        : real(path as never, init as never)) as never);
    renderApp("/campaigns");
    await screen.findByRole("table");
    const c = campaigns[0]!;
    await userEvent.click(within(row(c.label)).getByRole("button", { name: `Download MISP for ${c.label}` }));
    expect(await within(row(c.label)).findByRole("alert")).toHaveTextContent("Export failed: Exports require a configured live database (501)");
    expect(saved.names).toEqual([]);
  });
});
