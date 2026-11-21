import { QueryClient, QueryClientProvider, useQuery, type UseQueryResult } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiRequestError } from "@/api/client";
import { QueryState } from "./QueryState";

type Item = { id: string };

/** Minimal fake for the four branches QueryState reads; everything else is irrelevant here. */
function fakeQuery<T>(state: Partial<UseQueryResult<T>>): UseQueryResult<T> {
  return {
    isPending: false,
    isError: false,
    error: null,
    data: undefined,
    refetch: vi.fn(),
    ...state,
  } as unknown as UseQueryResult<T>;
}

/** Real TanStack Query wiring: one query, no retries, rendered through QueryState. */
function renderWithQuery(queryFn: () => Promise<Item[]>, props: { emptyText?: string; isEmpty?: (d: Item[]) => boolean } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  function Harness() {
    const query = useQuery({ queryKey: ["items"], queryFn });
    return (
      <QueryState query={query} {...props}>
        {(items) => (
          <ul aria-label="items">
            {items.map((i) => (
              <li key={i.id}>{i.id}</li>
            ))}
          </ul>
        )}
      </QueryState>
    );
  }
  return render(
    <QueryClientProvider client={client}>
      <Harness />
    </QueryClientProvider>,
  );
}

describe("QueryState", () => {
  it("shows a loading status while the query is pending", () => {
    renderWithQuery(() => new Promise<Item[]>(() => {}));
    expect(screen.getByRole("status", { name: "Loading" })).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
  });

  it("shows an alert with the ApiRequestError message and status", async () => {
    renderWithQuery(() => Promise.reject(new ApiRequestError(404, { error: "not_found", detail: "Incident not found" })));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Could not load data: Incident not found (404)");
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("shows a generic message for non-API errors without leaking the raw error text", async () => {
    renderWithQuery(() => Promise.reject(new Error("socket hang up at 10.0.0.1")));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Could not load data: Unexpected error.");
    expect(alert).not.toHaveTextContent("socket hang up");
  });

  it("Retry calls query.refetch", async () => {
    const refetch = vi.fn();
    const query = fakeQuery<Item[]>({ isError: true, error: new ApiRequestError(500, undefined), refetch });
    render(<QueryState query={query}>{() => <p>data</p>}</QueryState>);
    expect(screen.getByRole("alert")).toHaveTextContent("Request failed with status 500 (500)");
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it("Retry re-runs a real failed query and then renders the data", async () => {
    const queryFn = vi
      .fn<() => Promise<Item[]>>()
      .mockRejectedValueOnce(new ApiRequestError(503, { error: "unavailable", detail: "Backend warming up" }))
      .mockResolvedValueOnce([{ id: "inc_synthetic_1" }]);
    renderWithQuery(queryFn);
    expect(await screen.findByRole("alert")).toHaveTextContent("Backend warming up (503)");
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("inc_synthetic_1")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(queryFn).toHaveBeenCalledTimes(2);
  });

  it("shows the default empty text when isEmpty returns true and does not call children", () => {
    const children = vi.fn(() => <p>should not render</p>);
    const query = fakeQuery<Item[]>({ data: [] });
    render(
      <QueryState query={query} isEmpty={(d) => d.length === 0}>
        {children}
      </QueryState>,
    );
    expect(screen.getByText("Nothing to show yet.")).toBeInTheDocument();
    expect(children).not.toHaveBeenCalled();
  });

  it("shows a custom empty text from a real query that resolved to []", async () => {
    renderWithQuery(() => Promise.resolve([]), { isEmpty: (d) => d.length === 0, emptyText: "No incidents in the review queue." });
    expect(await screen.findByText("No incidents in the review queue.")).toBeInTheDocument();
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
  });

  it("renders children with the data when the query succeeds", async () => {
    renderWithQuery(() => Promise.resolve([{ id: "inc_synthetic_a" }, { id: "inc_synthetic_b" }]), { isEmpty: (d) => d.length === 0 });
    const list = await screen.findByRole("list", { name: "items" });
    expect(list.querySelectorAll("li")).toHaveLength(2);
    expect(screen.queryByText("Nothing to show yet.")).not.toBeInTheDocument();
  });

  it("renders data (not the empty state) when isEmpty is omitted, even for an empty array", () => {
    const query = fakeQuery<Item[]>({ data: [] });
    render(<QueryState query={query}>{(d) => <p>{`${d.length} items`}</p>}</QueryState>);
    expect(screen.getByText("0 items")).toBeInTheDocument();
    expect(screen.queryByText("Nothing to show yet.")).not.toBeInTheDocument();
  });
});
