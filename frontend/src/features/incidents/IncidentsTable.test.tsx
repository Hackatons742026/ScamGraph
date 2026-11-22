import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it } from "vitest";
import type { IncidentSummary } from "@/api/types";
import { incidents } from "@/mocks/data";
import { IncidentsTable } from "./IncidentsTable";

function renderTable(rows: IncidentSummary[]) {
  const router = createMemoryRouter([{ path: "/", element: <IncidentsTable incidents={rows} /> }]);
  render(<RouterProvider router={router} />);
}

describe("IncidentsTable", () => {
  it("sorts numbered folder labels numerically, not character by character", async () => {
    const base = incidents[0]!;
    renderTable(["10", "2", "1", "36"].map((label) => ({ ...base, id: `inc_${label}`, label })));

    const table = screen.getByRole("table");
    await userEvent.click(within(table).getByRole("button", { name: /Incident/i }));
    const labels = within(table)
      .getAllByRole("link")
      .filter((el) => el.getAttribute("href")?.startsWith("/incidents/"))
      .map((el) => el.textContent);
    expect(labels).toEqual(["1", "2", "10", "36"]);
  });
});
