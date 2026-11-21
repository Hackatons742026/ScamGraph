import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiRequestError } from "@/api/client";
import { campaigns } from "@/mocks/data";
import { renderApp } from "@/test/render";
import * as overrideApi from "./api";

const alpha = campaigns.find((c) => c.id === "camp_alpha")!;
const beta = campaigns.find((c) => c.id === "camp_beta")!;
const row = (label: string) => screen.getByRole("link", { name: label }).closest("tr")!;

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Campaign merge and split overrides", () => {
  it("merges selected campaigns and refreshes the campaigns query", async () => {
    const merge = vi.spyOn(overrideApi, "mergeCampaigns");
    const invalidate = vi.spyOn(overrideApi, "invalidateAfterOverride");
    renderApp("/campaigns");
    await screen.findByRole("table");
    await userEvent.click(within(row(alpha.label)).getByRole("checkbox", { name: `Select ${alpha.label}` }));
    await userEvent.click(within(row(beta.label)).getByRole("checkbox", { name: `Select ${beta.label}` }));
    await userEvent.click(screen.getByRole("button", { name: /Merge selected/ }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent(alpha.label);
    expect(dialog).toHaveTextContent(beta.label);
    await userEvent.click(within(dialog).getByRole("button", { name: "Merge" }));
    await waitFor(() => expect(merge).toHaveBeenCalledWith({ campaign_ids: [alpha.id, beta.id], note: undefined }));
    await waitFor(() => expect(invalidate).toHaveBeenCalled());
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("shows merge errors inline without closing the dialog", async () => {
    vi.spyOn(overrideApi, "mergeCampaigns").mockRejectedValueOnce(
      new ApiRequestError(501, { error: "not_implemented", detail: "Analyst overrides are enabled after core freeze." }),
    );
    renderApp("/campaigns");
    await screen.findByRole("table");
    await userEvent.click(within(row(alpha.label)).getByRole("checkbox", { name: `Select ${alpha.label}` }));
    await userEvent.click(within(row(beta.label)).getByRole("checkbox", { name: `Select ${beta.label}` }));
    await userEvent.click(screen.getByRole("button", { name: /Merge selected/ }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Merge" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(/501/);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("splits selected members after loading campaign detail", async () => {
    const split = vi.spyOn(overrideApi, "splitCampaign");
    const invalidate = vi.spyOn(overrideApi, "invalidateAfterOverride");
    renderApp("/campaigns");
    await screen.findByRole("table");
    await userEvent.click(within(row(alpha.label)).getByRole("button", { name: "Split" }));
    const dialog = await screen.findByRole("dialog");
    expect(await within(dialog).findByText("Synthetic incident Alpha-1")).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("checkbox", { name: "Synthetic incident Alpha-2" }));
    await userEvent.click(within(dialog).getByRole("button", { name: "Split" }));
    await waitFor(() =>
      expect(split).toHaveBeenCalledWith({ campaign_id: alpha.id, incident_ids: ["inc_alpha_2"], note: undefined }),
    );
    await waitFor(() => expect(invalidate).toHaveBeenCalled());
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("shows split errors inline", async () => {
    vi.spyOn(overrideApi, "splitCampaign").mockRejectedValueOnce(
      new ApiRequestError(501, { error: "not_implemented", detail: "Analyst overrides are enabled after core freeze." }),
    );
    renderApp("/campaigns");
    await screen.findByRole("table");
    await userEvent.click(within(row(alpha.label)).getByRole("button", { name: "Split" }));
    const dialog = await screen.findByRole("dialog");
    await within(dialog).findByText("Synthetic incident Alpha-1");
    await userEvent.click(within(dialog).getByRole("checkbox", { name: "Synthetic incident Alpha-1" }));
    await userEvent.click(within(dialog).getByRole("button", { name: "Split" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(/not_implemented|core freeze|501/i);
  });
});
