import { describe, expect, it } from "vitest";
import { formatDate, humanize, ignoreReasonLabel } from "./domain";

describe("humanize", () => {
  it("turns snake_case evidence types into words", () => {
    expect(humanize("meta_pixel_id")).toBe("meta pixel id");
    expect(humanize("iban")).toBe("iban");
  });
});

describe("formatDate", () => {
  it("keeps the ISO date part (no locale or timezone shift) and shows an em dash when missing", () => {
    expect(formatDate("2026-11-03T23:59:00Z")).toBe("2026-11-03");
    expect(formatDate(null)).toBe("—");
  });
});

describe("ignoreReasonLabel", () => {
  it("labels known reasons, falls back for unknown ones, and accepts null or a missing field (optional in the live OpenAPI)", () => {
    expect(ignoreReasonLabel("cdn_ip")).toBe("CDN / shared-hosting IP");
    expect(ignoreReasonLabel("future_reason")).toBe("Ignored by rule");
    expect(ignoreReasonLabel(null)).toBeNull();
    expect(ignoreReasonLabel(undefined)).toBeNull();
  });
});
