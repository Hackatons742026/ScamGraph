import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it } from "vitest";
import type { ClassifyResult, Outcome } from "@/api/types";
import { OUTCOME } from "@/lib/domain";
import { evidence, incidents } from "@/mocks/data";
import { OutcomeCard } from "./OutcomeCard";

function baseResult(outcome: Outcome, overrides: Partial<ClassifyResult> = {}): ClassifyResult {
  const known = incidents.find((i) => i.outcome === "known_campaign")!;
  return {
    outcome,
    campaign_id: outcome === "known_campaign" ? known.campaign_id : null,
    campaign_label: outcome === "known_campaign" ? known.campaign_label : null,
    reasons: [
      {
        kind: outcome === "needs_review" ? "coverage" : outcome === "known_campaign" ? "match" : "weak",
        text: `Synthetic reason for ${outcome}`,
        evidence: outcome === "known_campaign" ? [evidence.pixel] : [],
      },
    ],
    coverage: known.coverage,
    evidence: [],
    candidate_edges: [],
    elapsed_ms: 42,
    ...overrides,
  };
}

function renderCard(result: ClassifyResult) {
  const router = createMemoryRouter(
    [{ path: "/", element: <OutcomeCard result={result} /> }, { path: "/campaigns", element: <div>Campaigns</div> }],
    { initialEntries: ["/"] },
  );
  return render(<RouterProvider router={router} />);
}

describe("OutcomeCard", () => {
  it.each([
    ["known_campaign", /Synthetic reason for known_campaign/],
    ["new_candidate", /Synthetic reason for new_candidate/],
    ["needs_review", /Synthetic reason for needs_review/],
  ] as const)("renders %s with reasons", (outcome, reason) => {
    const result = baseResult(outcome);
    renderCard(result);

    expect(screen.getByRole("heading", { name: "Classification outcome" })).toBeInTheDocument();
    expect(screen.getByText(OUTCOME[outcome])).toBeInTheDocument();
    expect(screen.getByText(reason)).toBeInTheDocument();

    if (outcome === "known_campaign") {
      const link = screen.getByRole("link", { name: result.campaign_label! });
      expect(link).toHaveAttribute("href", `/campaigns/${result.campaign_id}`);
    } else {
      expect(screen.queryByRole("link")).not.toBeInTheDocument();
    }
  });
});
