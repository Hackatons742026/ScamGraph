import { cleanup, fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as client from "@/api/client";
import { ApiRequestError } from "@/api/client";
import { ignoreReasonLabel, OUTCOME, TIER } from "@/lib/domain";
import { incidentDetail, incidents } from "@/mocks/data";
import { renderApp } from "@/test/render";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Incident detail page", () => {
  it("renders decision, evidence, coverage and failed artifacts", async () => {
    const alpha2 = incidents.find((i) => i.id === "inc_alpha_2")!;
    const detail = incidentDetail(alpha2.id)!;
    renderApp(`/incidents/${alpha2.id}`);

    expect(await screen.findByRole("heading", { level: 1, name: "Incident detail" })).toBeInTheDocument();
    expect(await screen.findByText(alpha2.label)).toBeInTheDocument();

    // Coverage badges from the summary.
    expect(screen.getByText("full coverage")).toBeInTheDocument();

    // Decision card for one of the three outcomes (OutcomeBadge also appears in the header).
    const decisionCard = screen.getByRole("heading", { name: "Decision" }).closest(".rounded-lg") as HTMLElement;
    expect(within(decisionCard).getByText(OUTCOME[detail.outcome!])).toBeInTheDocument();

    // Evidence shows tier + masked display (never invent raw ids as the primary value).
    const evidenceCard = screen.getByRole("heading", { name: "Evidence" }).closest(".rounded-lg") as HTMLElement;
    expect(within(evidenceCard).getAllByRole("img", { name: new RegExp(`^${TIER.A.label}`) }).length).toBeGreaterThan(0);
    expect(within(evidenceCard).getByText("pixel_****1111")).toBeInTheDocument();

    // Evidence names its source artifact; raw artifact ids are never shown.
    expect(within(evidenceCard).getAllByText("step_2.har").length).toBeGreaterThan(0);
    expect(within(evidenceCard).queryByText("art_alpha2_har")).not.toBeInTheDocument();

    // Ignored evidence is muted with a reason.
    expect(within(evidenceCard).getByText(new RegExp(`Ignored: ${ignoreReasonLabel("cdn_ip")}`))).toBeInTheDocument();

    // Failed artifacts call out the reason.
    expect(screen.getByText(/1 failed artifact/i)).toBeInTheDocument();
    expect(screen.getByText(/Unrecognised format/i)).toBeInTheDocument();
  });

  it("lists each funnel step's redirect hops", async () => {
    renderApp("/incidents/inc_alpha_1");
    const hops = await screen.findByRole("list", { name: "Redirects in step 1" });
    expect(within(hops).getAllByRole("listitem")).toHaveLength(2);
    // Hops show host and path; the full redacted URL stays available as a tooltip.
    expect(within(hops).getByText("click.example-scam.test/click")).toHaveAttribute(
      "title",
      "https://click.example-scam.test/click",
    );
    expect(within(hops).getByText("news.example-scam.test/a?…")).toBeInTheDocument();
    expect(hops).toHaveTextContent("302 →");
  });

  it("loads artifact detail from GET /api/artifacts/{id}", async () => {
    renderApp("/incidents/inc_alpha_1");
    expect(await screen.findByText(/Synthetic incident Alpha-1/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /capture\.har/i }));
    expect(await screen.findByText(/42 requests/i)).toBeInTheDocument();
    expect(screen.getByText(/Hosts:.*news\.example-scam\.test/)).toBeInTheDocument();
  });

  it("shows the existing exact-duplicate indicator from artifact detail", async () => {
    renderApp("/incidents/inc_alpha_2");
    await userEvent.click(await screen.findByRole("button", { name: /article\.html/i }));
    expect(await screen.findByText("art_alpha1_page")).toBeInTheDocument();
    expect(screen.getByText(/Duplicate of/)).toBeInTheDocument();
  });

  it("shows an artifact's screenshots with OCR text and enlarges one in place", async () => {
    renderApp("/incidents/inc_alpha_1");
    await userEvent.click(await screen.findByRole("button", { name: /ad_screenshot\.png/i }));

    const gallery = await screen.findByRole("region", { name: "Media" });
    const images = within(gallery).getAllByRole("img");
    expect(images.map((img) => img.getAttribute("alt"))).toEqual(["Screenshot 1", "Screenshot 2", "Screenshot 3"]);
    // Mock mode never requests real media: every tile is the synthetic placeholder.
    for (const img of images) expect(img.getAttribute("src")).toMatch(/^data:image\/svg\+xml/);
    expect(within(gallery).getAllByText(/OCR: Synthetic OCR text/)).toHaveLength(3);

    await userEvent.click(within(gallery).getByRole("button", { name: "Enlarge Screenshot 2" }));
    const enlarged = within(gallery).getByRole("figure", { name: "Enlarged Screenshot 2" });
    expect(within(enlarged).getByRole("img", { name: "Screenshot 2" })).toBeInTheDocument();
    expect(within(enlarged).getByRole("button", { name: "Close enlarged media" })).toHaveFocus();

    await userEvent.click(within(enlarged).getByRole("button", { name: "Close enlarged media" }));
    expect(within(gallery).queryByRole("figure", { name: /Enlarged/ })).not.toBeInTheDocument();
  });

  it("labels video frames by timestamp and falls back to text when an image fails to load", async () => {
    renderApp("/incidents/inc_delta");
    await userEvent.click(await screen.findByRole("button", { name: /screen_recording\.mp4/i }));

    const gallery = await screen.findByRole("region", { name: "Media" });
    const frames = within(gallery).getAllByRole("img");
    expect(frames.map((img) => img.getAttribute("alt"))).toEqual(["Video frame at 0.0 s", "Video frame at 2.0 s", "Video frame at 4.0 s"]);

    fireEvent.error(frames[1]!);
    expect(within(gallery).getByRole("img", { name: "Video frame at 2.0 s (unavailable)" })).toHaveTextContent("Image unavailable");
    expect(within(gallery).queryByRole("button", { name: "Enlarge Video frame at 2.0 s" })).not.toBeInTheDocument();
    expect(within(gallery).getByRole("button", { name: "Enlarge Video frame at 4.0 s" })).toBeInTheDocument();
  });

  it("shows no media section for artifacts without media", async () => {
    renderApp("/incidents/inc_alpha_1");
    await userEvent.click(await screen.findByRole("button", { name: /capture\.har/i }));
    expect(await screen.findByText(/42 requests/i)).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Media" })).not.toBeInTheDocument();
  });

  it("shows loading then data", async () => {
    renderApp("/incidents/inc_gamma");
    expect(screen.getByRole("status", { name: "Loading" })).toBeInTheDocument();
    expect(await screen.findByText(/Synthetic incident Gamma/)).toBeInTheDocument();
    expect(screen.queryByRole("status", { name: "Loading" })).not.toBeInTheDocument();
  });

  it("shows empty state for unknown incident id", async () => {
    renderApp("/incidents/missing_incident");
    expect(await screen.findByText(/Incident not found/i)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows error state when the API fails", async () => {
    vi.spyOn(client, "unwrap").mockRejectedValueOnce(
      new ApiRequestError(503, { error: "unavailable", detail: "Incident service down" }),
    );
    renderApp("/incidents/inc_alpha_1");
    expect(await screen.findByRole("alert")).toHaveTextContent(/Incident service down/);
  });

  it("renders all three decision outcomes across fixtures", async () => {
    for (const outcome of ["known_campaign", "new_candidate", "needs_review"] as const) {
      cleanup();
      const row = incidents.find((i) => i.outcome === outcome)!;
      renderApp(`/incidents/${row.id}`);
      expect(await screen.findByText(row.label)).toBeInTheDocument();
      const decisionCard = screen.getByRole("heading", { name: "Decision" }).closest(".rounded-lg") as HTMLElement;
      expect(within(decisionCard).getByText(OUTCOME[outcome])).toBeInTheDocument();
    }
  });
});
