// @vitest-environment node
// Node env: jsdom's File/FormData can't be serialised by Node's native Request (multipart with files hangs).
import { describe, expect, it } from "vitest";
import { api, ApiRequestError, unwrap } from "@/api/client";
import { mockFetch } from "./handlers";

describe("mock transport covers contract v1", () => {
  it("serves health, runs and import", async () => {
    expect((await unwrap(api.GET("/api/health"))).status).toBe("ok");
    const run = await unwrap(api.GET("/api/runs/latest"));
    expect(run.status).toBe("done");
    expect((await unwrap(api.GET("/api/runs/{run_id}", { params: { path: { run_id: run.id } } }))).id).toBe(run.id);
    const started = await api.POST("/api/import", { body: {} });
    expect(started.response.status).toBe(202);
    expect(started.data?.run_id).toBe(run.id);
  });

  it("filters incidents by status (review queue) and campaign", async () => {
    const all = await unwrap(api.GET("/api/incidents"));
    const queue = await unwrap(api.GET("/api/incidents", { params: { query: { status: "needs_review,unassigned" } } }));
    expect(queue.length).toBeGreaterThan(0);
    expect(queue.length).toBeLessThan(all.length);
    expect(queue.every((i) => i.status === "needs_review" || i.status === "unassigned")).toBe(true);
    const camp = await unwrap(api.GET("/api/incidents", { params: { query: { campaign: all[0]!.campaign_id! } } }));
    expect(camp.every((i) => i.campaign_id === all[0]!.campaign_id || i.network_id === all[0]!.campaign_id)).toBe(true);
  });

  it("serves incident, artifact, campaign, links and graph details", async () => {
    const [first] = await unwrap(api.GET("/api/incidents"));
    const detail = await unwrap(api.GET("/api/incidents/{incident_id}", { params: { path: { incident_id: first!.id } } }));
    expect(detail.evidence.every((e) => typeof e.display === "string" && e.tier)).toBe(true);
    const artifact = await unwrap(api.GET("/api/artifacts/{artifact_id}", { params: { path: { artifact_id: detail.artifacts[0]!.id } } }));
    expect(artifact.id).toBe(detail.artifacts[0]!.id);
    const [camp] = await unwrap(api.GET("/api/campaigns"));
    expect((await unwrap(api.GET("/api/campaigns/{campaign_id}", { params: { path: { campaign_id: camp!.id } } }))).members.length).toBe(camp!.size);
    expect(Array.isArray(await unwrap(api.GET("/api/campaigns/{campaign_id}/links", { params: { path: { campaign_id: camp!.id } } })))).toBe(true);
    const graph = await unwrap(api.GET("/api/graph", { params: { query: { tiers: "A" } } }));
    expect(graph.edges.length).toBeGreaterThan(0);
    expect(graph.edges.every((e) => e.tier === "A")).toBe(true);
    expect((await unwrap(api.GET("/api/eval/report"))).scenarios).toHaveLength(7);
  });

  it("serves masked synthetic exports for campaigns only, 404 for networks and unknown ids", async () => {
    const all = await unwrap(api.GET("/api/campaigns"));
    const camp = all.find((c) => c.level === "campaign")!;
    const net = all.find((c) => c.level === "network")!;
    const csv = await mockFetch(new Request(`http://localhost/api/exports/${camp.id}.csv`));
    expect(csv.headers.get("Content-Type")).toMatch(/^text\/csv/);
    expect(csv.headers.get("Content-Disposition")).toMatch(/^attachment; filename="scamgraph-campaign-[0-9a-f]{16}\.csv"$/);
    const text = await csv.text();
    expect(text).toMatch(/^record_type,campaign_ref,incident_ref\n/);
    expect(text).not.toContain(camp.id);
    const misp = await mockFetch(new Request(`http://localhost/api/exports/${camp.id}.misp.json`));
    expect(JSON.parse(await misp.text()).Event.info).toMatch(/synthetic/);
    expect((await mockFetch(new Request(`http://localhost/api/exports/${net.id}.csv`))).status).toBe(404);
    expect((await mockFetch(new Request("http://localhost/api/exports/camp_missing.html"))).status).toBe(404);
  });

  it("returns contract errors: 404 for unknown ids, 501 for overrides", async () => {
    await expect(unwrap(api.GET("/api/incidents/{incident_id}", { params: { path: { incident_id: "missing" } } }))).rejects.toMatchObject({ status: 404, code: "not_found" });
    // The live OpenAPI declares no path param or body for the not-yet-enabled override routes (#9), so the typed
    // client can't build this request: exercise the mock transport directly with a real URL and contract body.
    const res = await mockFetch(new Request("http://localhost/api/edges/edge_alpha/decision", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ decision: "confirm", note: "Synthetic note" }),
    }));
    expect(res.status).toBe(501);
    expect(await res.json()).toMatchObject({ error: "not_implemented" });
  });

  it("classify returns all three outcomes and validates empty input", async () => {
    const post = (fd: FormData) => unwrap(api.POST("/api/classify", { body: fd as never, bodySerializer: (b) => b as FormData }));
    const [known] = await unwrap(api.GET("/api/incidents", { params: { query: { status: "in_campaign" } } }));
    const loo = new FormData();
    loo.set("exclude_incident", known!.id);
    loo.set("text", "synthetic");
    expect((await post(loo)).outcome).toBe("known_campaign");
    const video = new FormData();
    video.append("files", new File(["x"], "clip.mp4", { type: "video/mp4" }));
    expect((await post(video)).outcome).toBe("needs_review");
    const url = new FormData();
    url.set("url", "https://offer.example-scam.test/");
    expect((await post(url)).outcome).toBe("new_candidate");
    const err = await post(new FormData()).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiRequestError);
    expect(err).toMatchObject({ status: 422, code: "validation_error" });
  });

  it("classify returns 413 when uploaded files exceed CLASSIFY_MAX_UPLOAD_BYTES", async () => {
    const { CLASSIFY_MAX_UPLOAD_BYTES, classify } = await import("@/api/client");
    const oversized = new File([new Uint8Array(CLASSIFY_MAX_UPLOAD_BYTES + 1)], "huge.bin", { type: "application/octet-stream" });
    const err = await classify({ files: [oversized] }).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiRequestError);
    expect(err).toMatchObject({ status: 413, code: "payload_too_large", message: "Upload exceeds the size limit" });
  });
});
