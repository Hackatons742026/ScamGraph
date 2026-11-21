import createClient from "openapi-fetch";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiRequestError, CLASSIFY_MAX_UPLOAD_BYTES, classify, mediaUrl, unwrap } from "./client";
import type { paths } from "./schema";

/** Shape of an openapi-fetch result, built by hand so each case is explicit. */
const result = <T>(status: number, fields: { data?: T; error?: unknown }) =>
  Promise.resolve({ ...fields, response: { status, ok: status >= 200 && status < 300 } as Response });

/** A real openapi-fetch client whose transport always answers with `res` (no network). */
const clientReturning = (res: () => Response) =>
  createClient<paths>({ baseUrl: "http://localhost", fetch: async () => res() });

describe("unwrap", () => {
  it("returns data on success", async () => {
    await expect(unwrap(result(200, { data: { status: "ok", version: "1" } }))).resolves.toEqual({ status: "ok", version: "1" });
  });

  it("throws ApiRequestError with status, code and detail from the error body", async () => {
    const err = await unwrap(result(404, { error: { error: "not_found", detail: "Incident not found" } })).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiRequestError);
    expect(err).toBeInstanceOf(Error);
    expect(err).toMatchObject({ status: 404, code: "not_found", message: "Incident not found" });
  });

  it("reads FastAPI's default validation body ({detail: [{msg}]}) instead of showing [object Object]", async () => {
    const body = { detail: [{ loc: ["body", "files"], msg: "Field required", type: "missing" }, { msg: "Too large" }] };
    await expect(unwrap(result(422, { error: body }))).rejects.toMatchObject({ status: 422, code: "validation_error", message: "Field required; Too large" });
    await expect(unwrap(result(500, { error: { detail: { nested: true } } }))).rejects.toMatchObject({ message: "Request failed with status 500", code: "unknown_error" });
  });

  it("treats a 2xx with an empty body (e.g. 204) as success, not an error", async () => {
    await expect(unwrap(result(204, {}))).resolves.toBeUndefined();
  });

  it("falls back to a generic message and code when there is no error body", async () => {
    const err = await unwrap(result(500, {})).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiRequestError);
    expect(err).toMatchObject({ status: 500, code: "unknown_error", message: "Request failed with status 500" });
  });

  it("falls back per field when the error body is partial", async () => {
    await expect(unwrap(result(422, { error: { error: "validation_error" } }))).rejects.toMatchObject({
      status: 422, code: "validation_error", message: "Request failed with status 422",
    });
    await expect(unwrap(result(400, { error: { detail: "Bad tiers filter" } }))).rejects.toMatchObject({
      status: 400, code: "unknown_error", message: "Bad tiers filter",
    });
  });

  it("throws when the error body is not JSON (openapi-fetch hands back raw text)", async () => {
    const api = clientReturning(() => new Response("Bad Gateway", { status: 502, headers: { "Content-Type": "text/plain" } }));
    await expect(unwrap(api.GET("/api/health"))).rejects.toMatchObject({
      status: 502, code: "unknown_error", message: "Request failed with status 502",
    });
  });

  it("parses a contract ErrorResponse coming through a real openapi-fetch client", async () => {
    const api = clientReturning(
      () => new Response(JSON.stringify({ error: "not_found", detail: "Campaign not found" }), { status: 404, headers: { "Content-Type": "application/json" } }),
    );
    const err = await unwrap(api.GET("/api/campaigns/{campaign_id}", { params: { path: { campaign_id: "camp_missing" } } })).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiRequestError);
    expect(err).toMatchObject({ status: 404, code: "not_found", message: "Campaign not found" });
  });
});

describe("mediaUrl", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it("returns a synthetic data: URI in mock mode and never hits /api/media", () => {
    for (const id of ["med_1", "art_alpha1_shot_m0", "../../etc/passwd", ""]) {
      const url = mediaUrl(id);
      expect(url.startsWith("data:image/svg+xml")).toBe(true);
      expect(url).not.toContain("/api/media");
      expect(decodeURIComponent(url)).toContain("synthetic media");
    }
    // Same placeholder regardless of id: no media id leaks into the URL.
    expect(mediaUrl("a")).toBe(mediaUrl("b"));
  });

  it("returns an encoded /api/media URL when mock mode is off", async () => {
    vi.stubEnv("VITE_USE_MOCKS", "false");
    vi.resetModules();
    const live = await import("./client");
    expect(live.mediaUrl("med_1")).toBe("/api/media/med_1");
    expect(live.mediaUrl("a/../b c")).toBe("/api/media/a%2F..%2Fb%20c");
  });
});

describe("classify wrapper", () => {
  it("documents the 10 MB upload cap shared with the mock", () => {
    expect(CLASSIFY_MAX_UPLOAD_BYTES).toBe(10_000_000);
  });

  it("posts multipart fields and returns ClassifyResult (mock transport)", async () => {
    // Prefer text-only: jsdom File/FormData + Node Request can hang on file parts.
    const result = await classify({
      files: [],
      text: "synthetic wrapper note",
      url: "https://offer.example-scam.test/",
    });
    expect(result.outcome).toBe("new_candidate");
    expect(result.reasons.length).toBeGreaterThan(0);
    expect(typeof result.elapsed_ms).toBe("number");
  });
});
