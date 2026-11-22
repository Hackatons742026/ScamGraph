import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as client from "@/api/client";
import { ApiRequestError } from "@/api/client";
import type { Edge } from "@/api/types";
import { EdgeDecisionActions } from "./EdgeDecisionActions";
import { MOCK_EDGE_FAIL_ID } from "@/mocks/sentinels";
import * as overrideApi from "./api";

function renderActions(edgeId = "edge_alpha", analyst_override: Edge["analyst_override"] = null) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const invalidate = vi.spyOn(qc, "invalidateQueries");
  render(
    <QueryClientProvider client={qc}>
      <EdgeDecisionActions edge={{ id: edgeId, analyst_override }} />
    </QueryClientProvider>,
  );
  return { invalidate };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("EdgeDecisionActions", () => {
  it("confirms an edge, shows recorded_at, and refreshes graph/campaigns/incidents", async () => {
    const { invalidate } = renderActions();
    await userEvent.click(screen.getByRole("button", { name: "Confirm" }));
    expect(await screen.findByRole("status")).toHaveTextContent(/Confirmed · recorded at 2026-11-21T22:00:00Z/);
    await waitFor(() => {
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ["graph"] });
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ["campaigns"] });
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ["incidents"] });
    });
  });

  it("rejects an edge and shows recorded_at", async () => {
    renderActions();
    await userEvent.type(screen.getByLabelText(/Note/), "Synthetic reject note");
    await userEvent.click(screen.getByRole("button", { name: "Reject" }));
    expect(await screen.findByRole("status")).toHaveTextContent(/Rejected · recorded at/);
  });

  it("shows the persisted decision, time, and note passed in the edge payload", () => {
    renderActions("edge_saved", {
      decision: "confirm",
      recorded_at: "2026-11-21T22:00:00Z",
      note: "Reviewed the shared tier-A pixel",
    });
    expect(screen.getByRole("status")).toHaveTextContent(
      "Confirmed · recorded at 2026-11-21T22:00:00Z · Note: Reviewed the shared tier-A pixel",
    );
  });

  it("shows inline errors including 501 not_implemented", async () => {
    vi.spyOn(overrideApi, "postEdgeDecision").mockRejectedValueOnce(
      new ApiRequestError(501, { error: "not_implemented", detail: "Analyst overrides are enabled after core freeze." }),
    );
    renderActions(MOCK_EDGE_FAIL_ID);
    await userEvent.click(screen.getByRole("button", { name: "Confirm" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/not enabled on this server/i);
    expect(screen.getByRole("alert")).toHaveTextContent(/not enabled on this server/i);
  });

  it("surfaces ApiRequestError from unwrap without a detail", async () => {
    vi.spyOn(client, "unwrap").mockRejectedValueOnce(new ApiRequestError(502, undefined));
    renderActions();
    await userEvent.click(screen.getByRole("button", { name: "Reject" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Request failed with status 502");
    expect(alert).not.toHaveTextContent("(502)");
  });
});
