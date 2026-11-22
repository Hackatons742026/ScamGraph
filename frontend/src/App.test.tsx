import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { incidents } from "@/mocks/data";
import { renderApp } from "@/test/render";

describe("app shell (mock mode)", () => {
  it("renders navigation, mock banner and live mock data on Overview", async () => {
    renderApp("/");
    const nav = screen.getByRole("navigation", { name: "Main" });
    expect(within(nav).getAllByRole("link")).toHaveLength(7);
    expect(screen.getByRole("note")).toHaveTextContent(/synthetic data only/i);
    expect(await screen.findByText("Latest run")).toBeInTheDocument();
    const main = screen.getByRole("main");
    expect(within(main).getByText("Incidents").closest("div")).toHaveTextContent(String(incidents.length));
  });

  it.each([
    ["/", "Overview"],
    ["/incidents", "Incidents"],
    ["/incidents/inc_x", "Incident detail"],
    ["/campaigns", "Campaigns"],
    ["/campaigns/camp_x", "Campaign detail"],
    ["/graph", "Investigation graph"],
    ["/classify", "Classify new material"],
    ["/review", "Review queue"],
    ["/evaluation", "Evaluation"],
  ])("route %s renders its page", (path, heading) => {
    renderApp(path);
    expect(screen.getByRole("heading", { level: 1, name: heading })).toBeInTheDocument();
  });

  it("navigates via the sidebar", async () => {
    renderApp("/");
    await userEvent.click(screen.getByRole("link", { name: /Review queue/ }));
    expect(screen.getByRole("heading", { level: 1, name: "Review queue" })).toBeInTheDocument();
  });

  it("shows a not-found page for unknown routes", () => {
    renderApp("/nope");
    expect(screen.getByRole("heading", { level: 1, name: "Page not found" })).toBeInTheDocument();
  });
});
