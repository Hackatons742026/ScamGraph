import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Coverage, Family, IncidentStatus, Outcome, Tier } from "@/api/types";
import { badgeVariants } from "@/components/ui/badge";
import { STATUS } from "@/lib/domain";
import { CoverageBadges, FamilyLabel, OutcomeBadge, StatusBadge, TierBadge } from "./badges";

// Exhaustive by type: adding a value to the contract enum breaks the type check until it is listed here.
const TIERS = Object.keys({ A: 1, B: 1, C: 1 } satisfies Record<Tier, 1>) as Tier[];
const FAMILIES = Object.keys({ kit: 1, tds: 1, domain: 1, creative: 1, hosting: 1 } satisfies Record<NonNullable<Family>, 1>) as NonNullable<Family>[];
const OUTCOMES = Object.keys({ known_campaign: 1, new_candidate: 1, needs_review: 1 } satisfies Record<Outcome, 1>) as Outcome[];
const STATUSES = Object.keys({
  in_campaign: 1,
  unassigned: 1,
  needs_review: 1,
  new_candidate: 1,
} satisfies Record<IncidentStatus, 1>) as IncidentStatus[];

const classesOf = (variant: "default" | "warning" | "success" | "danger" | "outline") => badgeVariants({ variant }).split(" ");

const coverage = (level: Coverage["level"], badges: string[]): Coverage => ({
  artifact_kinds: ["video"], has_har: false, has_page: false, has_image: false, has_video: true, has_adlib: false,
  has_text: false, level, badges,
});

describe("TierBadge", () => {
  const expected: Record<Tier, RegExp> = {
    A: /^Tier A: .*links incidents on its own/i,
    B: /^Tier B: .*two families/i,
    C: /^Tier C: .*adds to the score only/i,
  };

  it.each(TIERS)("tier %s shows its letter with an accessible hint", (tier) => {
    render(<TierBadge tier={tier} />);
    const badge = screen.getByRole("img", { name: expected[tier] });
    expect(badge).toHaveTextContent(new RegExp(`^${tier}$`));
    // Hover hint for sighted users matches the part after "Tier X: " in the accessible label.
    expect(badge.getAttribute("aria-label")).toBe(`Tier ${tier}: ${badge.getAttribute("title")}`);
  });

  it("uses a distinct colour per tier", () => {
    const colours = TIERS.map((tier) => {
      const { unmount } = render(<TierBadge tier={tier} />);
      const colour = screen.getByText(tier).style.backgroundColor;
      unmount();
      return colour;
    });
    expect(colours.every(Boolean)).toBe(true);
    expect(new Set(colours).size).toBe(TIERS.length);
  });
});

describe("FamilyLabel", () => {
  it("renders nothing for a null family", () => {
    const { container } = render(<FamilyLabel family={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  const labels: Record<NonNullable<Family>, string> = {
    kit: "Site kit",
    tds: "Click tracking (TDS)",
    domain: "Domain",
    creative: "Creative",
    hosting: "Hosting",
  };

  it.each(FAMILIES)("family %s renders a human label with a decorative dot", (family) => {
    const { container } = render(<FamilyLabel family={family} />);
    expect(container.textContent).toBe(labels[family]);
    const dot = container.querySelector("[aria-hidden]");
    expect(dot).not.toBeNull();
    expect(dot).toBeEmptyDOMElement();
  });
});

describe("CoverageBadges", () => {
  it('shows "full coverage" (success) when there are no badges', () => {
    render(<CoverageBadges coverage={coverage("ok", [])} />);
    expect(screen.getByText("full coverage")).toHaveClass(...classesOf("success"));
  });

  it("never shows full coverage when level is low but no gaps are named", () => {
    render(<CoverageBadges coverage={coverage("low", [])} />);
    expect(screen.queryByText("full coverage")).not.toBeInTheDocument();
    expect(screen.getByText("low coverage")).toHaveClass(...classesOf("warning"));
  });

  it("shows one warning badge per gap when level is low", () => {
    render(<CoverageBadges coverage={coverage("low", ["no HAR", "video only"])} />);
    expect(screen.queryByText("full coverage")).not.toBeInTheDocument();
    for (const text of ["no HAR", "video only"]) {
      expect(screen.getByText(text)).toHaveClass(...classesOf("warning"));
    }
  });

  it("uses neutral (non-warning) badges when level is ok", () => {
    render(<CoverageBadges coverage={coverage("ok", ["no image"])} />);
    const badge = screen.getByText("no image");
    expect(badge).toHaveClass(...classesOf("default"));
    expect(badge).not.toHaveClass("bg-amber-50");
  });
});

describe("OutcomeBadge", () => {
  const labels: Record<Outcome, string> = {
    known_campaign: "Known Campaign",
    new_candidate: "New Campaign Candidate",
    needs_review: "Needs Review",
  };

  it.each(OUTCOMES)("outcome %s has a human label", (outcome) => {
    render(<OutcomeBadge outcome={outcome} />);
    expect(screen.getByText(labels[outcome])).toBeInTheDocument();
    expect(screen.queryByText(outcome)).not.toBeInTheDocument();
  });

  it("styles the three outcomes differently", () => {
    const classNames = OUTCOMES.map((outcome) => {
      const { unmount } = render(<OutcomeBadge outcome={outcome} />);
      const cls = screen.getByText(labels[outcome]).className;
      unmount();
      return cls;
    });
    expect(new Set(classNames).size).toBe(3);
  });

  it('shows "no decision" for a null outcome', () => {
    render(<OutcomeBadge outcome={null} />);
    expect(screen.getByText("no decision")).toBeInTheDocument();
  });
});

describe("StatusBadge", () => {
  it.each(STATUSES)("status %s has a human label", (status) => {
    render(<StatusBadge status={status} />);
    expect(screen.getByText(STATUS[status])).toBeInTheDocument();
    expect(screen.queryByText(status)).not.toBeInTheDocument();
  });
});
