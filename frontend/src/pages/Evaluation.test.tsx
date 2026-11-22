import { screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as client from "@/api/client";
import { ApiRequestError } from "@/api/client";
import type { EvalReport } from "@/api/types";
import { evalReport, incidents } from "@/mocks/data";
import { renderApp } from "@/test/render";

const pct = (x: number) => `${Math.round(x * 100)}%`;
const section = (title: string) => screen.getByRole("heading", { name: title }).closest("div.rounded-lg") as HTMLElement;
const zero = { precision: 0, recall: 0, f1: 0, tp: 0, fp: 0, fn: 0 };

/** The page also loads /api/incidents (for LOO links): replace only the eval report's result, whatever the call order. */
const stubReport = (result: () => Promise<EvalReport>) =>
  vi.spyOn(client, "unwrap").mockImplementation(async (request) => {
    const { data } = await request;
    return (data && typeof data === "object" && "scenarios" in data ? result() : data) as never;
  });

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Evaluation", () => {
  it("renders every report section from the contract shape", async () => {
    renderApp("/evaluation");
    await screen.findByRole("heading", { name: "Validation scenarios" });
    expect(screen.queryByText(/Not from a labelled evaluation run/)).not.toBeInTheDocument(); // (the mock-mode banner is also a note)

    const scenarios = section("Validation scenarios");
    const passed = evalReport.scenarios.filter((s) => s.passed).length;
    expect(scenarios).toHaveTextContent(`${passed} of ${evalReport.scenarios.length} scenarios pass`);
    expect(within(scenarios).getAllByRole("row")).toHaveLength(evalReport.scenarios.length + 1);
    const failed = evalReport.scenarios.find((s) => !s.passed)!;
    expect(within(scenarios).getByText(failed.name).closest("tr")).toHaveTextContent(new RegExp(`Fail.*${failed.details}`));

    const pairs = section("Pair metrics");
    expect(pairs).toHaveTextContent(`False merges: ${evalReport.false_merges}`);
    expect(pairs).toHaveTextContent(new RegExp(`Campaign level.*Precision${pct(evalReport.pairs.campaign.precision)}.*Recall${pct(evalReport.pairs.campaign.recall)}`));
    expect(pairs).toHaveTextContent(`${evalReport.pairs.n_pairs} labelled pairs`);

    const loo = section("Leave-one-out routing");
    expect(loo).toHaveTextContent(`Routing accuracy ${pct(evalReport.loo.accuracy)}`);
    const matrix = within(loo).getByRole("table", { name: "Confusion matrix" });
    const cells = within(matrix).getAllByRole("cell").map((c) => Number(c.textContent));
    expect(cells).toEqual(evalReport.loo.confusion.matrix.flat());
    const looTable = within(loo).getByRole("table", { name: /per incident/ });
    expect(within(looTable).getAllByRole("row")).toHaveLength(evalReport.loo.rows.length + 1);
    const first = incidents.find((i) => i.id === evalReport.loo.rows[0]!.incident_id)!;
    expect(await within(looTable).findByRole("link", { name: first.label })).toHaveAttribute("href", `/incidents/${first.id}`);

    const ablation = section("Ablation");
    expect(within(ablation).getAllByRole("row")).toHaveLength(evalReport.ablation.length + 1);
  });

  it("renders the live shape honestly: synthetic cases, nothing claimed from absent labels", async () => {
    // Mirrors GET /api/eval/report on a backend without labels (built-in synthetic suite only).
    const live: EvalReport = {
      generated_at: null,
      scenarios: [
        { id: 1, name: "Exact tier-A match", criterion: "known_campaign", passed: true, details: "expected known_campaign; got known_campaign" },
        { id: 5, name: "Low coverage", criterion: "needs_review", passed: true, details: "expected needs_review; got needs_review" },
      ],
      pairs: { n_pairs: 0, mentor_verified: 0, agreement: null, campaign: zero, network: zero },
      false_merges: 0,
      loo: {
        accuracy: 1,
        rows: [{ incident_id: "loo-synthetic-a", expected: "known_campaign", predicted: "known_campaign", correct: true }],
        confusion: { labels: ["known_campaign", "new_candidate", "needs_review"], matrix: [[1, 0, 0], [0, 0, 0], [0, 0, 0]] },
      },
      ablation: [{ config: "all-signals", campaign_p: 0, campaign_r: 0, false_merges: 0, loo_routing: 1 }],
    };
    stubReport(async () => live);
    renderApp("/evaluation");
    expect(await screen.findByText(/Not a labelled evaluation of your imported dataset/)).toHaveAttribute(
      "role",
      "note",
    );

    const pairs = section("Pair metrics");
    expect(pairs).toHaveTextContent("False merges: not measured");
    expect(pairs).toHaveTextContent(/precision, recall, F1 and false merges are not measured/);
    expect(within(pairs).queryByText(/^0%$/)).not.toBeInTheDocument();

    const ablation = section("Ablation");
    expect(ablation).toHaveTextContent(/Ablation needs labelled pairs/);
    expect(within(ablation).queryByRole("table")).not.toBeInTheDocument();

    const scenarios = section("Validation scenarios");
    expect(scenarios).toHaveTextContent("expected Known Campaign; got Known Campaign");
    expect(scenarios).not.toHaveTextContent("known_campaign");

    const loo = section("Leave-one-out routing");
    expect(loo).toHaveTextContent(/Synthetic fixtures only/);
    expect(within(loo).getByText("synthetic fixtures")).toBeInTheDocument();
    expect(within(loo).getByText("loo-synthetic-a")).toBeInTheDocument();
    expect(within(loo).queryByRole("link")).not.toBeInTheDocument();
  });

  it("never calls a routing case synthetic while the incident list is unknown", async () => {
    vi.spyOn(client, "unwrap").mockImplementation(async (request) => {
      const { data } = await request;
      if (Array.isArray(data)) throw new ApiRequestError(500, { error: "server_error", detail: "Incidents unavailable" });
      return data as never;
    });
    renderApp("/evaluation");
    const id = evalReport.loo.rows[0]!.incident_id;
    await screen.findByRole("heading", { name: "Leave-one-out routing" });
    const cell = await within(section("Leave-one-out routing")).findByText(id);
    expect(cell).not.toHaveAttribute("title");
    expect(within(section("Leave-one-out routing")).queryByRole("link")).not.toBeInTheDocument();
  });

  it("shows an honest empty state when the evaluation has not run", async () => {
    const empty: EvalReport = {
      generated_at: null, scenarios: [], false_merges: 0, ablation: [],
      pairs: { n_pairs: 0, mentor_verified: 0, agreement: null, campaign: zero, network: zero },
      loo: { accuracy: 0, rows: [], confusion: { labels: [], matrix: [] } },
    };
    stubReport(async () => empty);
    renderApp("/evaluation");
    expect(await screen.findByText(/evaluation has not been run yet/)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Pair metrics" })).not.toBeInTheDocument();
  });

  it("shows the error state", async () => {
    stubReport(() => Promise.reject(new ApiRequestError(500, { error: "server_error", detail: "Report unavailable" })));
    renderApp("/evaluation");
    expect(await screen.findByRole("alert")).toHaveTextContent(/Report unavailable/);
  });
});
