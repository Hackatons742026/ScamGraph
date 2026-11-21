import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { EvidenceItem } from "@/api/types";
import { LinkEvidence } from "./LinkEvidence";

const ev = (id: string, p: Partial<EvidenceItem> = {}): EvidenceItem => ({
  id, type: "pixel_id", tier: "B", family: null, display: `val_${id}`, weight: 1, artifact_id: `art_${id}`,
  funnel_step: null, ignored: false, ignore_reason: null, detail: null, ...p,
});
const items = () => screen.getAllByRole("listitem");

describe("LinkEvidence", () => {
  it("lists strongest first (tier, then weight) and ignored items last with their reason", () => {
    render(<LinkEvidence evidence={[
      ev("c9", { tier: "C", weight: 9 }),
      ev("cdn", { tier: "A", weight: 9, ignored: true, ignore_reason: "cdn_ip" }),
      ev("b1", { weight: 1 }),
      ev("a1", { tier: "A", weight: 1 }),
      ev("b5", { weight: 5 }),
    ]} />);
    expect(items().map((li) => within(li).getByText(/^val_/).textContent)).toEqual(["val_a1", "val_b5", "val_b1", "val_c9", "val_cdn"]);
    expect(within(items()[0]!).getByRole("img", { name: /^Tier A/ })).toBeInTheDocument();
    expect(items()[4]).toHaveTextContent("Ignored: CDN / shared-hosting IP");
    expect(items()[0]).not.toHaveTextContent("Ignored");
  });

  it("shows type, family, source artifact and funnel step, with no step text when it is unknown", () => {
    // Step 0 (the ad) is a real step and must not be treated as missing.
    render(<LinkEvidence evidence={[ev("kit", { type: "kit_hash", family: "kit", funnel_step: 0 }), ev("phone", { tier: "C" })]} />);
    const [kit, phone] = items();
    expect(kit).toHaveTextContent("kit hash");
    expect(kit).toHaveTextContent("Site kit");
    expect(kit).toHaveTextContent("from art_kit · funnel step 0");
    expect(phone).toHaveTextContent("from art_phone");
    expect(phone).not.toHaveTextContent("funnel step");
  });

  it("explains when a link has no evidence", () => {
    render(<LinkEvidence evidence={[]} />);
    expect(screen.getByText("No shared evidence recorded for this link.")).toBeInTheDocument();
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
  });
});
