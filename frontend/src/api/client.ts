import createClient from "openapi-fetch";
import { USE_MOCKS } from "@/lib/env";
import type { ClassifyResult } from "./types";
import type { paths } from "./schema";

/** Matches backend live classify body cap (`len(body) > 10_000_000`). */
/** Server defaults (SCAMGRAPH_MAX_UPLOAD_FILE_MB / _REQUEST_MB): real HAR captures and videos exceed 10 MB. */
export const CLASSIFY_MAX_FILE_BYTES = 50 * 1024 * 1024;
export const CLASSIFY_MAX_UPLOAD_BYTES = 100 * 1024 * 1024;

export type ClassifyInput = {
  files: File[];
  text?: string;
  url?: string;
  exclude_incident?: string;
};

export const api = createClient<paths>({
  // Absolute base: Node's Request rejects relative URLs (tests). Browsers always have location.
  baseUrl: globalThis.location?.origin ?? "http://localhost",
  // Inline env check + dynamic import: a live build drops the mock transport and all fixtures.
  ...(import.meta.env.VITE_USE_MOCKS === "true"
    ? { fetch: async (req: Request) => (await import("@/mocks/handlers")).mockFetch(req) }
    : {}),
});

/** Reads a contract `{error, detail}` body, tolerating FastAPI's default `{detail: [{msg}]}` validation shape. */
function parseErrorBody(body: unknown): { code?: string; detail?: string } {
  if (!body || typeof body !== "object") return {};
  const b = body as Record<string, unknown>;
  if (Array.isArray(b.detail)) {
    const msgs = b.detail
      .map((d) => (d && typeof d === "object" ? (d as Record<string, unknown>).msg : undefined))
      .filter((m): m is string => typeof m === "string");
    return { code: typeof b.error === "string" ? b.error : "validation_error", detail: msgs.join("; ") || undefined };
  }
  return {
    code: typeof b.error === "string" ? b.error : undefined,
    detail: typeof b.detail === "string" ? b.detail : undefined,
  };
}

export class ApiRequestError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, body: unknown) {
    const { code, detail } = parseErrorBody(body);
    super(detail ?? `Request failed with status ${status}`);
    this.status = status;
    this.code = code ?? "unknown_error";
  }
}

/** Turns an openapi-fetch result into data or a thrown ApiRequestError (for TanStack Query). */
export async function unwrap<T>(
  call: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  const { data, error, response } = await call;
  if (error !== undefined || !response.ok) {
    throw new ApiRequestError(response.status, error);
  }
  // 2xx with an empty body (e.g. 204) is a success; openapi-fetch reports it as data === undefined.
  return data as T;
}

/** URL for <img> tags. Mock mode never touches real media. */
export function mediaUrl(id: string): string {
  if (USE_MOCKS) {
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180"><rect width="100%" height="100%" fill="#e2e8f0"/><text x="50%" y="50%" font-family="sans-serif" font-size="14" fill="#64748b" text-anchor="middle">synthetic media</text></svg>`;
    return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
  }
  return `/api/media/${encodeURIComponent(id)}`;
}

/**
 * POST /api/classify as multipart. Builds FormData and holds the only cast
 * (generated OpenAPI body types `files` as `string[]`).
 */
export async function classify(input: ClassifyInput): Promise<ClassifyResult> {
  const fd = new FormData();
  for (const file of input.files) {
    fd.append("files", file);
  }
  const text = input.text?.trim();
  const url = input.url?.trim();
  if (text) fd.set("text", text);
  if (url) fd.set("url", url);
  if (input.exclude_incident) fd.set("exclude_incident", input.exclude_incident);

  return unwrap(
    api.POST("/api/classify", {
      // Generated multipart schema uses files?: string[]; FormData is the runtime body.
      body: fd as never,
      bodySerializer: (b) => b as FormData,
    }),
  );
}
