import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as client from "@/api/client";
import { ApiRequestError } from "@/api/client";
import type { ClassifyResult, Outcome } from "@/api/types";
import { OUTCOME } from "@/lib/domain";
import { evidence, incidents } from "@/mocks/data";
import { renderApp } from "@/test/render";

afterEach(() => {
  vi.restoreAllMocks();
});

function classifyResult(outcome: Outcome): ClassifyResult {
  const known = incidents.find((i) => i.outcome === "known_campaign")!;
  return {
    outcome,
    campaign_id: outcome === "known_campaign" ? known.campaign_id : null,
    campaign_label: outcome === "known_campaign" ? known.campaign_label : null,
    reasons: [
      {
        kind: outcome === "needs_review" ? "coverage" : outcome === "known_campaign" ? "match" : "weak",
        text: `Page reason for ${outcome}`,
        evidence: outcome === "known_campaign" ? [evidence.pixel] : [],
      },
    ],
    coverage: known.coverage,
    evidence: [],
    candidate_edges: [],
    elapsed_ms: 55,
  };
}

describe("Classify page", () => {
  it("renders the form and leave-one-out options from GET /api/incidents", async () => {
    renderApp("/classify");
    expect(await screen.findByRole("heading", { level: 1, name: "Classify new material" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Classify/i })).toBeDisabled();

    const loo = await screen.findByLabelText(/Leave one out/i);
    expect(loo).toBeEnabled();
    for (const row of incidents) {
      expect(within(loo).getByRole("option", { name: row.label })).toBeInTheDocument();
    }
  });

  it("submits pasted text via classify() and shows the outcome card", async () => {
    const spy = vi.spyOn(client, "classify").mockResolvedValue(classifyResult("new_candidate"));
    renderApp("/classify");
    await screen.findByLabelText(/Leave one out/i);

    await userEvent.type(screen.getByLabelText(/Pasted text/i), "synthetic note");
    await userEvent.click(screen.getByRole("button", { name: /^Classify$/i }));

    await waitFor(() => expect(spy).toHaveBeenCalledTimes(1));
    expect(spy.mock.calls[0]![0]).toEqual({
      files: [],
      text: "synthetic note",
      url: undefined,
      exclude_incident: undefined,
    });

    const card = (await screen.findByRole("heading", { name: "Classification outcome" })).closest(
      ".rounded-lg",
    ) as HTMLElement;
    expect(within(card).getByText(OUTCOME.new_candidate)).toBeInTheDocument();
    expect(within(card).getByText(/Page reason for new_candidate/)).toBeInTheDocument();
  });

  it("sends exclude_incident when leave-one-out is selected", async () => {
    const known = incidents.find((i) => i.outcome === "known_campaign")!;
    const spy = vi.spyOn(client, "classify").mockResolvedValue(classifyResult("known_campaign"));
    renderApp("/classify");
    const loo = await screen.findByLabelText(/Leave one out/i);
    expect(await within(loo).findByRole("option", { name: known.label })).toBeInTheDocument();

    await userEvent.selectOptions(loo, known.id);
    await userEvent.type(screen.getByLabelText(/^URL$/i), "https://offer.example-scam.test/");
    await userEvent.click(screen.getByRole("button", { name: /^Classify$/i }));

    await waitFor(() => expect(spy).toHaveBeenCalled());
    expect(spy.mock.calls[0]![0]).toEqual({
      files: [],
      text: undefined,
      url: "https://offer.example-scam.test/",
      exclude_incident: known.id,
    });
    expect(await screen.findByText(OUTCOME.known_campaign)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: known.campaign_label! })).toHaveAttribute("href", `/campaigns/${known.campaign_id}`);
  });

  it("mock mode says the result is synthetic and nothing was saved", async () => {
    const spy = vi.spyOn(client, "classify").mockResolvedValue(classifyResult("new_candidate"));
    renderApp("/classify");
    await screen.findByLabelText(/Leave one out/i);
    expect(screen.getByText(/Mock mode: results come from synthetic data and nothing is saved/)).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText(/Pasted text/i), "synthetic note");
    await userEvent.click(screen.getByRole("button", { name: /^Classify$/i }));

    await waitFor(() => expect(spy).toHaveBeenCalledTimes(1));
    const status = await screen.findByText(/Demo mode: nothing was saved/);
    expect(status.closest("[role=status]")).toHaveTextContent(/later uploads are not compared with it/);
    expect(screen.queryByText(/Saved to live memory/)).not.toBeInTheDocument();
  });

  it("accepts a 16 MB capture and blocks a file over 50 MB before sending", async () => {
    renderApp("/classify");
    await screen.findByLabelText(/Leave one out/i);
    const sized = (name: string, bytes: number) => {
      const file = new File(["{}"], name, { type: "application/json" });
      Object.defineProperty(file, "size", { value: bytes });
      return file;
    };
    const input = screen.getByLabelText(/Files/i) as HTMLInputElement;
    expect(screen.getByText(/Max 50 MB per file · 100 MB total/)).toBeInTheDocument();

    await userEvent.upload(input, sized("capture.har", 16 * 1024 * 1024));
    expect(screen.getByRole("button", { name: /^Classify$/i })).toBeEnabled();

    await userEvent.upload(input, sized("recording.mp4", 51 * 1024 * 1024));
    expect(screen.getByRole("button", { name: /^Classify$/i })).toBeDisabled();
    expect(screen.getByRole("alert")).toHaveTextContent("A file is larger than 50 MB");
  });

  it("surfaces ApiRequestError for oversized uploads (413)", async () => {
    vi.spyOn(client, "classify").mockRejectedValue(
      new ApiRequestError(413, { error: "payload_too_large", detail: "Upload exceeds the size limit" }),
    );
    renderApp("/classify");
    await screen.findByLabelText(/Leave one out/i);

    await userEvent.type(screen.getByLabelText(/Pasted text/i), "too big");
    await userEvent.click(screen.getByRole("button", { name: /^Classify$/i }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/Upload exceeds the size limit/);
    expect(alert).toHaveTextContent(/413/);
    expect(screen.queryByRole("heading", { name: "Classification outcome" })).not.toBeInTheDocument();
  });

  it("surfaces validation errors (422) when classify rejects", async () => {
    vi.spyOn(client, "classify").mockRejectedValue(
      new ApiRequestError(422, { error: "validation_error", detail: "At least one file, text, or URL is required." }),
    );
    renderApp("/classify");
    await screen.findByLabelText(/Leave one out/i);

    await userEvent.type(screen.getByLabelText(/Pasted text/i), "x");
    await userEvent.click(screen.getByRole("button", { name: /^Classify$/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/At least one file, text, or URL is required/);
  });

  it("shows all three outcomes via mocked classify results", async () => {
    for (const outcome of ["known_campaign", "new_candidate", "needs_review"] as const) {
      cleanup();
      vi.restoreAllMocks();
      const spy = vi.spyOn(client, "classify").mockResolvedValue(classifyResult(outcome));
      renderApp("/classify");
      await screen.findByLabelText(/Leave one out/i);
      await userEvent.type(screen.getByLabelText(/Pasted text/i), `input for ${outcome}`);
      await userEvent.click(screen.getByRole("button", { name: /^Classify$/i }));
      await waitFor(() => expect(spy).toHaveBeenCalled());
      const card = (await screen.findByRole("heading", { name: "Classification outcome" })).closest(
        ".rounded-lg",
      ) as HTMLElement;
      expect(within(card).getByText(OUTCOME[outcome])).toBeInTheDocument();
      expect(within(card).getByText(new RegExp(`Page reason for ${outcome}`))).toBeInTheDocument();
    }
  });
});
