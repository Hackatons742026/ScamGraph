import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as client from "@/api/client";
import { ApiRequestError } from "@/api/client";
import { STATUS } from "@/lib/domain";
import { incidents } from "@/mocks/data";
import { renderApp } from "@/test/render";

afterEach(() => {
  vi.restoreAllMocks();
});

const queueRows = incidents.filter((i) => i.status === "needs_review" || i.status === "unassigned");

describe("Review queue page", () => {
  it("lists needs_review and unassigned incidents with reasons", async () => {
    renderApp("/review");
    expect(await screen.findByRole("heading", { level: 1, name: "Review queue" })).toBeInTheDocument();

    expect(queueRows.length).toBeGreaterThan(0);
    for (const row of queueRows) {
      expect(await screen.findByRole("link", { name: row.label })).toHaveAttribute("href", `/incidents/${row.id}`);
      expect(screen.getByText(row.reason_summary!)).toBeInTheDocument();
    }

    expect(screen.getAllByText(STATUS.needs_review).length).toBeGreaterThan(0);
    expect(screen.getAllByText(STATUS.unassigned).length).toBeGreaterThan(0);

    // In-campaign incidents must not appear in the review queue.
    const inCampaign = incidents.find((i) => i.status === "in_campaign")!;
    expect(screen.queryByRole("link", { name: inCampaign.label })).not.toBeInTheDocument();
  });

  it("shows a loading state then the queue", async () => {
    renderApp("/review");
    expect(screen.getByRole("status", { name: "Loading" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: queueRows[0]!.label })).toBeInTheDocument();
    expect(screen.queryByRole("status", { name: "Loading" })).not.toBeInTheDocument();
  });

  it("shows an empty state when the queue is empty", async () => {
    vi.spyOn(client, "unwrap").mockResolvedValueOnce([]);
    renderApp("/review");
    expect(await screen.findByText(/No incidents need review/i)).toBeInTheDocument();
  });

  it("shows an error state when the API fails", async () => {
    vi.spyOn(client, "unwrap").mockRejectedValueOnce(
      new ApiRequestError(503, { error: "unavailable", detail: "Review queue unavailable" }),
    );
    renderApp("/review");
    expect(await screen.findByRole("alert")).toHaveTextContent(/Review queue unavailable/);
  });
});
