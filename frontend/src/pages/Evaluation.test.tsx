import { screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as client from "@/api/client";
import { ApiRequestError } from "@/api/client";
import type { EvalReport } from "@/api/types";
import { evalReport } from "@/mocks/data";
import { renderApp } from "@/test/render";

const pct = (x: number) => `${Math.round(x * 100)}%`;
const section = (title: string) => screen.getByRole("heading", { name: title }).closest("div.rounded-lg") as HTMLElement;
const zero = { precision: 0, recall: 0, f1: 0, tp: 0, fp: 0, fn: 0 };

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
    expect(within(within(loo).getByRole("table", { name: /per incident/ })).getAllByRole("row")).toHaveLength(evalReport.loo.rows.length + 1);

    const ablation = section("Ablation");
    expect(within(ablation).getAllByRole("row")).toHaveLength(evalReport.ablation.length + 1);
  });

  it("says when results are not from a labelled run and never shows unmeasured metrics as 0%", async () => {
    const synthetic: EvalReport = { ...evalReport, generated_at: null, pairs: { ...evalReport.pairs, n_pairs: 0, mentor_verified: 0, agreement: null, campaign: zero, network: zero } };
    vi.spyOn(client, "unwrap").mockResolvedValueOnce(synthetic);
    renderApp("/evaluation");
    expect(await screen.findByText(/Not from a labelled evaluation run/)).toHaveAttribute("role", "note");
    const pairs = section("Pair metrics");
    expect(pairs).toHaveTextContent(/precision, recall and F1 are not measured/);
    expect(within(pairs).queryByText("0%")).not.toBeInTheDocument();
    const ablationRow = within(section("Ablation")).getAllByRole("row")[1]!;
    expect(within(ablationRow).getAllByRole("cell").slice(1, 3).map((c) => c.textContent)).toEqual(["—", "—"]);
  });

  it("shows an honest empty state when the evaluation has not run", async () => {
    const empty: EvalReport = { ...evalReport, generated_at: null, scenarios: [], loo: { accuracy: 0, rows: [], confusion: { labels: [], matrix: [] } }, ablation: [] };
    vi.spyOn(client, "unwrap").mockResolvedValueOnce(empty);
    renderApp("/evaluation");
    expect(await screen.findByText(/evaluation has not been run yet/)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Pair metrics" })).not.toBeInTheDocument();
  });

  it("shows the error state", async () => {
    vi.spyOn(client, "unwrap").mockRejectedValueOnce(new ApiRequestError(500, { error: "server_error", detail: "Report unavailable" }));
    renderApp("/evaluation");
    expect(await screen.findByRole("alert")).toHaveTextContent(/Report unavailable/);
  });
});
