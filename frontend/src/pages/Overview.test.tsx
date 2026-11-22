import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as client from "@/api/client";
import { ApiRequestError } from "@/api/client";
import { latestRun } from "@/mocks/data";
import { renderApp } from "@/test/render";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Overview page", () => {
  it("renders run summary stats and artifact coverage", async () => {
    renderApp("/");
    expect(await screen.findByText("Latest run")).toBeInTheDocument();
    expect(screen.getByText("Artifact coverage")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /^Kind$/i })).toBeInTheDocument();
    expect(screen.getByText("har")).toBeInTheDocument();
    expect(within(screen.getByRole("main")).getByText("Incidents").closest("div")).toHaveTextContent(String(latestRun.incidents));
    expect(screen.getByRole("link", { name: /incidents list/i })).toHaveAttribute("href", "/incidents");
    expect(screen.getByText("Outside campaigns")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Outside campaigns/i })).toHaveAttribute(
      "href",
      "/incidents?status=new_candidate",
    );
    expect(screen.getByRole("link", { name: /New candidates/i })).toHaveAttribute(
      "href",
      "/incidents?status=new_candidate",
    );
    expect(screen.getByRole("link", { name: /Needs review/i })).toHaveAttribute("href", "/review");
  });

  it("shows loading then data", async () => {
    renderApp("/");
    expect(screen.getByRole("status", { name: "Loading" })).toBeInTheDocument();
    expect(await screen.findByText("Latest run")).toBeInTheDocument();
    expect(screen.queryByRole("status", { name: "Loading" })).not.toBeInTheDocument();
  });

  it("shows empty state when there is no latest run (404)", async () => {
    vi.spyOn(client, "unwrap").mockRejectedValueOnce(
      new ApiRequestError(404, { error: "not_found", detail: "No run yet" }),
    );
    renderApp("/");
    expect(await screen.findByText(/No analysis run yet/i)).toBeInTheDocument();
    expect(screen.queryByText("Latest run")).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows error state with retry", async () => {
    vi.spyOn(client, "unwrap").mockRejectedValueOnce(
      new ApiRequestError(503, { error: "unavailable", detail: "Backend down" }),
    );
    renderApp("/");
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/Backend down/);
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("triggers import and shows progress until the run settles", async () => {
    renderApp("/");
    expect(await screen.findByText("Latest run")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Run import/i }));
    expect(await screen.findByRole("button", { name: /Importing/i })).toBeDisabled();

    await waitFor(
      () => {
        expect(screen.getByRole("status")).toHaveTextContent(/Import finished|running|Waiting|Starting/i);
      },
      { timeout: 3000 },
    );

    await waitFor(
      () => {
        expect(screen.getByRole("button", { name: /Run import/i })).toBeEnabled();
      },
      { timeout: 3000 },
    );
    expect(screen.getByRole("status")).toHaveTextContent(/Import finished/i);
  });
});
