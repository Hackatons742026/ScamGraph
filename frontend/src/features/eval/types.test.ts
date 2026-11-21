import { describe, expect, it } from "vitest";
import { outcomeText, pct } from "./types";

describe("pct", () => {
  it("rounds to whole percent but never up to 100% or down to 0% it didn't reach", () => {
    expect(pct(0.8)).toBe("80%");
    expect(pct(1)).toBe("100%");
    expect(pct(0)).toBe("0%");
    expect(pct(0.996)).toBe(">99%");
    expect(pct(0.004)).toBe("<1%");
  });
});

describe("outcomeText", () => {
  it("replaces outcome codes with their labels and leaves other text alone", () => {
    expect(outcomeText("expected new_candidate; got needs_review")).toBe("expected New Campaign Candidate; got Needs Review");
    expect(outcomeText("Synthetic pass")).toBe("Synthetic pass");
  });
});
