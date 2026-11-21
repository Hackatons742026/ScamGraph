import { cleanup, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as client from "@/api/client";
import { ApiRequestError } from "@/api/client";
import { incidents } from "@/mocks/data";
import { STATUS } from "@/lib/domain";
import { renderApp } from "@/test/render";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Incidents page", () => {
  it("lists incidents and navigates to detail on row click", async () => {
    renderApp("/incidents");
    expect(await screen.findByRole("heading", { level: 1, name: "Incidents" })).toBeInTheDocument();
    const first = incidents[0]!;
    expect(await screen.findByRole("link", { name: first.label })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("link", { name: first.label }));
    expect(await screen.findByRole("heading", { level: 1, name: "Incident detail" })).toBeInTheDocument();
    expect(screen.getByText(new RegExp(first.id))).toBeInTheDocument();
  });

  it("filters by status and coverage", async () => {
    renderApp("/incidents");
    await screen.findByRole("link", { name: incidents[0]!.label });

    await userEvent.click(screen.getByRole("button", { name: STATUS.needs_review }));
    expect(screen.getByRole("button", { name: STATUS.needs_review })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("link", { name: /Delta/i })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Alpha-1/i })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Clear" }));
    expect(await screen.findByRole("link", { name: /Alpha-1/i })).toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText("Coverage"), "low");
    expect(screen.getByRole("link", { name: /Delta/i })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Alpha-1/i })).not.toBeInTheDocument();
  });

  it("sorts by column headers", async () => {
    renderApp("/incidents");
    await screen.findByRole("link", { name: incidents[0]!.label });

    const table = screen.getByRole("table");
    await userEvent.click(within(table).getByRole("button", { name: /Incident/i }));
    const labelsAsc = within(table)
      .getAllByRole("link")
      .map((el) => el.textContent);
    expect(labelsAsc).toEqual([...labelsAsc].sort((a, b) => a!.localeCompare(b!)));

    await userEvent.click(within(table).getByRole("button", { name: /Incident/i }));
    const labelsDesc = within(table)
      .getAllByRole("link")
      .map((el) => el.textContent);
    expect(labelsDesc).toEqual([...labelsAsc].reverse());
  });

  it("shows a loading state then the table", async () => {
    renderApp("/incidents");
    expect(screen.getByRole("status", { name: "Loading" })).toBeInTheDocument();
    expect(await screen.findByRole("table")).toBeInTheDocument();
  });

  it("shows an empty state when the API returns no incidents", async () => {
    vi.spyOn(client, "unwrap").mockResolvedValueOnce([]);
    renderApp("/incidents");
    expect(await screen.findByText(/No incidents yet/i)).toBeInTheDocument();
  });

  it("shows an error state when the API fails", async () => {
    vi.spyOn(client, "unwrap").mockRejectedValueOnce(
      new ApiRequestError(500, { error: "server_error", detail: "Incidents unavailable" }),
    );
    renderApp("/incidents");
    expect(await screen.findByRole("alert")).toHaveTextContent(/Incidents unavailable/);
  });

  it("shows a filter-empty message when nothing matches", async () => {
    renderApp("/incidents");
    await screen.findByRole("table");
    await userEvent.click(screen.getByRole("button", { name: STATUS.needs_review }));
    await userEvent.selectOptions(screen.getByLabelText("Coverage"), "ok");
    // Delta is needs_review + low coverage — no overlap with ok.
    expect(screen.getByText(/No incidents match these filters/i)).toBeInTheDocument();
    cleanup();
  });
});
