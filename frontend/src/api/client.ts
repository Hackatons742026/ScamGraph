import createClient from "openapi-fetch";
import { USE_MOCKS } from "@/lib/env";
import { mockFetch } from "@/mocks/handlers";
import type { paths } from "./schema";
import type { ApiError } from "./types";

export const api = createClient<paths>({
  // Absolute base: Node's Request rejects relative URLs (tests). Browsers always have location.
  baseUrl: globalThis.location?.origin ?? "http://localhost",
  ...(USE_MOCKS ? { fetch: mockFetch } : {}),
});

export class ApiRequestError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, body: Partial<ApiError> | undefined) {
    super(body?.detail ?? `Request failed with status ${status}`);
    this.status = status;
    this.code = body?.error ?? "unknown_error";
  }
}

/** Turns an openapi-fetch result into data or a thrown ApiRequestError (for TanStack Query). */
export async function unwrap<T>(
  call: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  const { data, error, response } = await call;
  if (error !== undefined || !response.ok) {
    throw new ApiRequestError(response.status, error as Partial<ApiError> | undefined);
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
