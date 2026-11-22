import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as client from "@/api/client";
import { ApiRequestError } from "@/api/client";
import type { ClassifyResult, IncidentSummary } from "@/api/types";
import { incidents } from "@/mocks/data";
import * as handlers from "@/mocks/handlers";
import { ClassifyForm } from "./ClassifyForm";

// Live UI behaviour. The transport stays the synthetic mock (VITE_USE_MOCKS is inlined in the client);
// only the UI's mode flag is switched, so the form behaves as it does against a live backend.
vi.mock("@/lib/env", () => ({ USE_MOCKS: false }));

const realMockFetch = handlers.mockFetch;

const uploaded: IncidentSummary = {
  ...incidents.find((i) => i.status === "new_candidate")!,
  id: "inc_upload_abcdef",
  label: "Upload abcdef",
};

const result: ClassifyResult = {
  outcome: "new_candidate",
  campaign_id: null,
  campaign_label: null,
  reasons: [{ kind: "weak", text: "Synthetic upload reason", evidence: [] }],
  coverage: uploaded.coverage,
  evidence: [],
  candidate_edges: [],
  elapsed_ms: 12,
};

const STALE_KEYS = [["campaigns"], ["graph", null, ["A", "B", "C"], ["campaign", "network"]], ["runs", "latest"], ["incidents", "inc_gamma"]];

type Backend = { saves: boolean; incidentsFailAfterSave?: boolean };

/** Classify resolves; a saving backend adds the uploaded incident to every later GET /api/incidents. */
function stubBackend({ saves, incidentsFailAfterSave = false }: Backend) {
  let classified = false;
  const classifySpy = vi.spyOn(client, "classify").mockImplementation(async () => {
    classified = true;
    return result;
  });
  const incidentReads = { count: 0 };
  vi.spyOn(handlers, "mockFetch").mockImplementation(async (req: Request) => {
    const isList = req.method === "GET" && new URL(req.url).pathname === "/api/incidents";
    if (isList) incidentReads.count += 1;
    if (isList && classified && incidentsFailAfterSave) {
      return Response.json({ error: "internal_error", detail: "Synthetic outage" }, { status: 500 });
    }
    const res = await realMockFetch(req);
    if (isList && classified && saves) return Response.json([...((await res.json()) as IncidentSummary[]), uploaded]);
    return res;
  });
  return { classifySpy, incidentReads };
}

function renderForm() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  for (const key of STALE_KEYS) queryClient.setQueryData(key, { seeded: true });
  const router = createMemoryRouter(
    [
      { path: "/classify", element: <ClassifyForm /> },
      { path: "/incidents", element: <p>Incidents page</p> },
      { path: "/incidents/:id", element: <p>Incident page</p> },
    ],
    { initialEntries: ["/classify"] },
  );
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return { queryClient, router };
}

async function submitText(text = "synthetic ad copy") {
  const loo = await screen.findByLabelText(/Leave one out/i);
  await waitFor(() => expect(loo).toBeEnabled());
  await userEvent.type(screen.getByLabelText(/Pasted text/i), text);
  await userEvent.click(screen.getByRole("button", { name: /^Classify$/i }));
}

const staleness = (queryClient: QueryClient) => STALE_KEYS.map((key) => queryClient.getQueryState(key)?.isInvalidated ?? false);

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ClassifyForm against a live backend", () => {
  it("explains before submitting that normal uploads are saved and leave-one-out is not", async () => {
    stubBackend({ saves: true });
    renderForm();
    expect(await screen.findByText(/each submission is saved as a new incident/)).toBeInTheDocument();
    expect(screen.getByText(/a leave-one-out run is never saved/)).toBeInTheDocument();
    expect(screen.queryByText(/Mock mode/)).not.toBeInTheDocument();
  });

  it("confirms a saved upload, links the new incident and refreshes incidents, campaigns, graph and run views", async () => {
    const { classifySpy } = stubBackend({ saves: true });
    const { queryClient, router } = renderForm();
    await submitText();

    const status = (await screen.findByText(/Saved to live memory as a new incident/)).closest("[role=status]") as HTMLElement;
    expect(classifySpy.mock.calls[0]![0]).toMatchObject({ exclude_incident: undefined });
    expect(status).toHaveTextContent(/Later uploads are compared with it/);
    expect(staleness(queryClient)).toEqual([true, true, true, true]);
    // The shared incident list was re-read: the leave-one-out picker now offers the upload too.
    expect(within(screen.getByLabelText(/Leave one out/i)).getByRole("option", { name: "Upload abcdef" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Classification outcome" })).toBeInTheDocument();

    await userEvent.click(within(status).getByRole("link", { name: "Open Upload abcdef" }));
    expect(router.state.location.pathname).toBe("/incidents/inc_upload_abcdef");
  });

  it("leave-one-out says nothing was saved and refreshes nothing", async () => {
    const { classifySpy, incidentReads } = stubBackend({ saves: true });
    const { queryClient } = renderForm();
    const loo = await screen.findByLabelText(/Leave one out/i);
    await waitFor(() => expect(loo).toBeEnabled());
    await userEvent.selectOptions(loo, "inc_gamma");
    await submitText();

    expect(await screen.findByText(/Leave-one-out: analysis only/)).toBeInTheDocument();
    expect(classifySpy.mock.calls[0]![0]).toMatchObject({ exclude_incident: "inc_gamma" });
    expect(staleness(queryClient)).toEqual([false, false, false, false]);
    expect(incidentReads.count).toBe(1);
    expect(screen.queryByText(/Saved to live memory/)).not.toBeInTheDocument();
  });

  it("says nothing was saved when the refreshed incident list is unchanged (server without a live database)", async () => {
    stubBackend({ saves: false });
    renderForm();
    await submitText();

    const status = (await screen.findByText(/^Not saved\.$/)).closest("[role=status]") as HTMLElement;
    expect(status).toHaveTextContent(/without a live database/);
    expect(screen.queryByText(/Saved to live memory/)).not.toBeInTheDocument();
  });

  it("still reports the save, with a link to Incidents, when the list cannot be re-read", async () => {
    stubBackend({ saves: true, incidentsFailAfterSave: true });
    const { queryClient } = renderForm();
    await submitText();

    const status = (await screen.findByText(/Saved to live memory for future comparison/)).closest("[role=status]") as HTMLElement;
    expect(within(status).getByRole("link", { name: "open Incidents" })).toHaveAttribute("href", "/incidents");
    expect(staleness(queryClient)).toEqual([true, true, true, true]);
    expect(screen.getByRole("heading", { name: "Classification outcome" })).toBeInTheDocument();
  });

  it("shows the backend's save failure and leaves cached views alone", async () => {
    vi.spyOn(client, "classify").mockRejectedValue(
      new ApiRequestError(500, { error: "internal_error", detail: "Uploaded material could not be saved for future analysis" }),
    );
    const { queryClient } = renderForm();
    await submitText();

    expect(await screen.findByRole("alert")).toHaveTextContent(/could not be saved for future analysis \(500\)/);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(staleness(queryClient)).toEqual([false, false, false, false]);
  });
});
