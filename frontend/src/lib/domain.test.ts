import { describe, expect, it } from "vitest";
import { formatDate, formatTimestamp, humanize, ignoreReasonLabel, shortUrl } from "./domain";

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

describe("formatTimestamp", () => {
  it("uses the browser's local date and time and handles missing or invalid values", () => {
    const expected = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" })
      .format(new Date("2026-11-03T23:59:00Z"));
    expect(formatTimestamp("2026-11-03T23:59:00Z")).toBe(expected);
    expect(formatTimestamp(null)).toBe("—");
    expect(formatTimestamp("not a timestamp")).toBe("—");
  });
});

describe("ignoreReasonLabel", () => {
  it("shortens URLs to host and path and hides query strings", () => {
    expect(shortUrl("https://offer.example-scam.test/landing?gclid=abc&x=1")).toBe("offer.example-scam.test/landing?…");
    expect(shortUrl("https://offer.example-scam.test/")).toBe("offer.example-scam.test");
    expect(shortUrl("not a url")).toBe("not a url");
    expect(shortUrl(`https://a.test/${"x".repeat(200)}`).length).toBe(80);
  });

  it("labels known reasons, falls back for unknown ones, and accepts null or a missing field (optional in the live OpenAPI)", () => {
    expect(ignoreReasonLabel("cdn_ip")).toBe("CDN / shared-hosting IP");
    expect(ignoreReasonLabel("platform_domain")).toBe("Shared platform domain (not operator infrastructure)");
    expect(ignoreReasonLabel("future_reason")).toBe("Ignored by rule");
    expect(ignoreReasonLabel(null)).toBeNull();
    expect(ignoreReasonLabel(undefined)).toBeNull();
  });
});
