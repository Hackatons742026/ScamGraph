// Data-safety guard for the mock fixtures: they must stay obviously synthetic.
import { describe, expect, it } from "vitest";
import source from "./data.ts?raw";
import * as db from "./data";

/** Everything the mock layer can serve, including values built by the detail functions. */
function allFixtures(): unknown[] {
  const incidentDetails = db.incidents.map((i) => db.incidentDetail(i.id));
  const artifactDetails = incidentDetails.flatMap((d) => d?.artifacts ?? []).map((a) => db.artifactDetail(a.id));
  return [
    db.evidence,
    db.incidents,
    db.edges,
    incidentDetails,
    artifactDetails,
    db.campaigns,
    db.campaigns.map((c) => db.campaignDetail(c.id)),
    db.campaigns.map((c) => db.campaignLinks(c.id)),
    db.graph,
    db.latestRun,
    db.evalReport,
  ];
}

/** Every string value (with its key) reachable from `value`. */
function strings(value: unknown, key = ""): Array<{ key: string; value: string }> {
  if (typeof value === "string") return [{ key, value }];
  if (Array.isArray(value)) return value.flatMap((v) => strings(v, key));
  if (value && typeof value === "object") return Object.entries(value).flatMap(([k, v]) => strings(v, k));
  return [];
}

/** Every string literal in the fixture source (double-quoted and template), so unexported values are covered too. */
const sourceLiterals = [...source.matchAll(/"((?:[^"\\\n]|\\.)*)"|`((?:[^`\\]|\\.)*)`/g)].map((m) => m[1] ?? m[2] ?? "");

// Hostname-shaped tokens. File names (capture.har, ad.info.json, ...) are excluded by extension below.
const HOST = /(?<![\w.@/-])(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z][a-z0-9-]*[a-z0-9](?![\w-])/gi;
const FILE_EXT = new Set(["har", "html", "htm", "mhtml", "json", "png", "jpg", "jpeg", "webp", "gif", "mp4", "webm", "mov", "bin", "txt", "zip", "ts", "tsx"]);

function domainsIn(text: string): string[] {
  const hosts = [...text.matchAll(HOST)].map((m) => m[0].toLowerCase());
  for (const m of text.matchAll(/[a-z][a-z0-9+.-]*:\/\/[^\s"'`)\]]+/gi)) hosts.push(new URL(m[0]).hostname.toLowerCase());
  return hosts.filter((h) => !FILE_EXT.has(h.split(".").pop()!));
}

const isTestDomain = (host: string) => host === "test" || host.endsWith(".test");

describe("mock fixtures are synthetic", () => {
  it("finds the fixture domains it is meant to check (guards against a vacuous pass)", () => {
    const found = new Set(strings(allFixtures()).flatMap((s) => domainsIn(s.value)));
    expect(found).toContain("offer.example-scam.test");
    expect(found).toContain("news.example-scam.test");
    expect(domainsIn("see https://shop.example.com/x and evil-offer.pl").sort()).toEqual(["evil-offer.pl", "shop.example.com"]);
    expect(domainsIn("capture.har ad.info.json ad_screenshot.png 0.81")).toEqual([]);
  });

  it("every domain in any served fixture value ends in .test", () => {
    const offenders = strings(allFixtures()).flatMap((s) => domainsIn(s.value).filter((d) => !isTestDomain(d)).map((d) => `${s.key}: ${d}`));
    expect(offenders).toEqual([]);
  });

  it("every domain in any string literal of data.ts ends in .test", () => {
    expect(sourceLiterals.length).toBeGreaterThan(50);
    const offenders = sourceLiterals.flatMap((lit) => domainsIn(lit).filter((d) => !isTestDomain(d)));
    expect(offenders).toEqual([]);
  });

  it("every URL in fixtures uses a .test host", () => {
    const urls = strings(allFixtures()).filter((s) => /^[a-z]+:\/\//i.test(s.value));
    expect(urls.length).toBeGreaterThan(0);
    for (const { value } of urls) expect(isTestDomain(new URL(value).hostname)).toBe(true);
  });

  it("evidence and other *display values never look like a raw IBAN or phone number", () => {
    const displays = strings(allFixtures()).filter((s) => s.key === "display" || s.key.endsWith("_display"));
    expect(displays.length).toBeGreaterThan(10);
    const offenders = displays.filter(({ value }) => {
      const compact = value.replace(/[\s()-]/g, ""); // separators people put inside IBANs and phone numbers
      const longDigitRun = /\d{9,}/.test(compact);
      const iban = /\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b/.test(compact);
      return longDigitRun || iban;
    });
    expect(offenders).toEqual([]);
  });

  it("the masking check itself rejects raw values and accepts masked ones", () => {
    const looksRaw = (v: string) => /\d{9,}/.test(v.replace(/[\s()-]/g, "")) || /\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b/.test(v.replace(/[\s()-]/g, ""));
    expect(looksRaw("+48 600 100 200")).toBe(true);
    expect(looksRaw("XX00 0000 0000 0000 0000 0000 0000")).toBe(true);
    expect(looksRaw("+48 *** *** 000")).toBe(false);
    expect(looksRaw("pixel_****1111")).toBe(false);
    expect(looksRaw("203.0.113.x")).toBe(false);
  });

  it("tracking parameters in URL displays are redacted", () => {
    const urls = strings(allFixtures()).filter((s) => s.key === "url_display");
    expect(urls.length).toBeGreaterThan(0);
    for (const { value } of urls) {
      for (const [param, v] of new URL(value).searchParams) {
        if (/^(fbclid|gclid|clickid|click_id|token|sid|session|key)$/i.test(param)) expect(v).toBe("[redacted]");
      }
    }
  });

  it("ignored evidence always carries an ignore reason (CDN IP, placeholder phone)", () => {
    const evidence = Object.values(db.evidence);
    expect(evidence.filter((e) => e.ignored).map((e) => e.ignore_reason).sort()).toEqual(["cdn_ip", "placeholder_phone"]);
    expect(evidence.filter((e) => e.ignored).every((e) => e.weight === 0)).toBe(true);
  });
});
