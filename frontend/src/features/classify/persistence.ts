import type { QueryClient } from "@tanstack/react-query";
import { api, unwrap } from "@/api/client";
import type { IncidentSummary } from "@/api/types";

/** Same cache entry as the Incidents page and the leave-one-out picker. */
export const INCIDENTS_KEY = ["incidents"] as const;
export const fetchIncidents = () => unwrap(api.GET("/api/incidents"));

/**
 * What became of the submitted material. ClassifyResult does not say, so the UI works it out:
 * a mock build never stores anything, leave-one-out is analysis only (contract), and otherwise
 * the incident list is read again and compared with the list from before the upload.
 */
export type SaveStatus =
  | { kind: "demo" }
  | { kind: "analysis_only" }
  /** The refreshed list holds incident(s) that were not there before: the upload is in live memory. */
  | { kind: "saved"; added: IncidentSummary[] }
  /** Live mode stores normal uploads, but the list could not be compared to show it. */
  | { kind: "saved_unverified" }
  /** The list was refreshed and is unchanged: the server has no live database and gave a demo answer. */
  | { kind: "not_saved" };

/** A saved upload changes incidents, links, campaigns and run counts: mark every view built from them stale. */
export function invalidateAfterUpload(client: QueryClient) {
  for (const queryKey of [["campaigns"], ["graph"], ["runs", "latest"]]) {
    void client.invalidateQueries({ queryKey });
  }
  // The list itself is re-read by refreshAfterUpload; detail and review entries refetch on their next mount.
  void client.invalidateQueries({ queryKey: INCIDENTS_KEY, refetchType: "none" });
}

/** Call after a successful live, non-leave-one-out classify. `before` is the cached incident list from before the upload. */
export async function refreshAfterUpload(
  client: QueryClient,
  before: readonly IncidentSummary[] | undefined,
): Promise<SaveStatus> {
  invalidateAfterUpload(client);
  let after: IncidentSummary[];
  try {
    after = await client.fetchQuery({ queryKey: INCIDENTS_KEY, queryFn: fetchIncidents, staleTime: 0 });
  } catch {
    return { kind: "saved_unverified" };
  }
  if (!before) return { kind: "saved_unverified" };
  const known = new Set(before.map((i) => i.id));
  const added = after.filter((i) => !known.has(i.id));
  return added.length ? { kind: "saved", added } : { kind: "not_saved" };
}
