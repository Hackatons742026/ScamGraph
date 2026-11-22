import { ApiRequestError } from "@/api/client";

const OVERRIDE_DISABLED =
  "Analyst overrides are not enabled on this server yet (confirm/reject and merge/split stay read-only).";

/** Prefer a stable analyst-facing message for 501; otherwise keep status once in the text. */
export function describeOverrideError(e: unknown): string {
  if (e instanceof ApiRequestError) {
    if (e.status === 501 || e.code === "not_implemented") return OVERRIDE_DISABLED;
    return e.message.includes(String(e.status)) ? e.message : `${e.message} (${e.status})`;
  }
  return e instanceof Error && e.message ? e.message : "network error";
}
