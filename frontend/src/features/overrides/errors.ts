import { ApiRequestError } from "@/api/client";

/** "Analyst overrides are enabled after core freeze (501)", but never "Request failed with status 502 (502)". */
export function describeOverrideError(e: unknown): string {
  if (e instanceof ApiRequestError) return e.message.includes(String(e.status)) ? e.message : `${e.message} (${e.status})`;
  return e instanceof Error && e.message ? e.message : "network error";
}
