import { api, ApiRequestError } from "@/api/client";

export const EXPORT_FORMATS = [
  { ext: "html", label: "Evidence pack", description: "HTML report with masked evidence" },
  { ext: "csv", label: "CSV", description: "spreadsheet of members and evidence" },
  { ext: "misp.json", label: "MISP", description: "MISP event JSON for threat-intel sharing" },
] as const;
export type ExportExt = (typeof EXPORT_FORMATS)[number]["ext"];

/**
 * Fetches GET /api/exports/{campaign}.{ext} and saves it under the server's filename. Fetching first (instead of a
 * plain link) turns 404/422/501 into an inline error rather than a downloaded error page; mock mode serves synthetic files.
 */
export async function downloadExport(campaignId: string, ext: ExportExt): Promise<string> {
  const { data, error, response } = await api.GET("/api/exports/{name}", {
    params: { path: { name: `${campaignId}.${ext}` } },
    parseAs: "blob",
  });
  if (error !== undefined || !response.ok || !(data instanceof Blob)) throw new ApiRequestError(response.status, error);
  const filename = /filename="([^"]+)"/.exec(response.headers.get("Content-Disposition") ?? "")?.[1] ?? `scamgraph-${campaignId}.${ext}`;
  const url = URL.createObjectURL(data);
  const link = Object.assign(document.createElement("a"), { href: url, download: filename });
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
  return filename;
}
