import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiRequestError } from "@/api/client";
import { campaigns } from "@/mocks/data";
import { downloadExport, REVOKE_AFTER_MS } from "./exports";

const campaign = campaigns.find((c) => c.level === "campaign")!;
const network = campaigns.find((c) => c.level === "network")!;
const names: string[] = [];

beforeEach(() => {
  names.length = 0;
  vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:synthetic");
  vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
    names.push(this.download);
  });
});
afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("downloadExport", () => {
  it("revokes the object URL only after a delay (Safari aborts blob downloads revoked too early)", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout"] });
    const name = await downloadExport(campaign.id, "html");
    expect(names).toEqual([name]);
    vi.advanceTimersByTime(REVOKE_AFTER_MS - 1);
    expect(URL.revokeObjectURL).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:synthetic");
  });

  it("turns error bodies into ApiRequestError through the real blob request path", async () => {
    await expect(downloadExport("camp_missing", "csv")).rejects.toMatchObject({ status: 404, message: "Campaign not found" });
    await expect(downloadExport(network.id, "csv")).rejects.toBeInstanceOf(ApiRequestError);
    expect(names).toEqual([]);
  });

  it("falls back to an id-free filename when the server sends none", async () => {
    vi.spyOn(api, "GET").mockResolvedValue({ data: new Blob(["x"]), error: undefined, response: new Response("x") } as never);
    expect(await downloadExport(campaign.id, "csv")).toBe("scamgraph-export.csv");
    expect(names[0]).not.toContain(campaign.id);
  });
});
