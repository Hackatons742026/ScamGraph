import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ImportRunButton } from "./ImportRunButton";

// Seeded cache entries for every view an import rewrites; the button must mark each stale when the run settles.
const AFFECTED = [
  ["runs", "latest"],
  ["incidents"],
  ["incidents", "inc_alpha_1"],
  ["artifacts", "art_alpha1_har"],
  ["campaigns"],
  ["campaigns", "camp_alpha"],
  ["graph", null, ["A", "B", "C"], ["campaign", "network"]],
];
const UNRELATED = ["eval-report"];

describe("ImportRunButton", () => {
  it("invalidates incidents, artifacts, campaigns and graph once the import finishes", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    for (const key of [...AFFECTED, UNRELATED]) client.setQueryData(key, { seeded: true });
    render(
      <QueryClientProvider client={client}>
        <ImportRunButton />
      </QueryClientProvider>,
    );

    await userEvent.click(screen.getByRole("button", { name: /Run import/i }));
    // Still running: nothing is invalidated before the run settles.
    expect(await screen.findByRole("button", { name: /Importing/i })).toBeDisabled();
    expect(client.getQueryState(["campaigns"])?.isInvalidated).toBe(false);

    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Import finished."), { timeout: 3000 });
    await waitFor(() => expect(AFFECTED.map((key) => client.getQueryState(key)?.isInvalidated)).toEqual(AFFECTED.map(() => true)));
    expect(client.getQueryState(UNRELATED)?.isInvalidated).toBe(false);
  });
});
