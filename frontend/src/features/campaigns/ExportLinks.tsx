import { Download } from "lucide-react";
import { useState } from "react";
import { ApiRequestError } from "@/api/client";
import { downloadExport, EXPORT_FORMATS, type ExportExt } from "./exports";

/** "Campaign not found (404)", but never "Request failed with status 502 (502)". */
function describe(e: unknown): string {
  if (e instanceof ApiRequestError) return e.message.includes(String(e.status)) ? e.message : `${e.message} (${e.status})`;
  return e instanceof Error && e.message ? e.message : "network error";
}

/** Per-campaign downloads: evidence pack (HTML), CSV and MISP. Failures show inline next to the buttons. */
export function ExportLinks({ campaignId, label }: { campaignId: string; label: string }) {
  const [busy, setBusy] = useState<ExportExt | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async (ext: ExportExt) => {
    if (busy) return; // aria-disabled, not disabled: the focused button keeps keyboard focus
    setBusy(ext);
    setError(null);
    try {
      await downloadExport(campaignId, ext);
    } catch (e) {
      setError(describe(e));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="flex flex-col gap-1">
      <div className="flex flex-wrap gap-1">
        {EXPORT_FORMATS.map((f) => (
          <button key={f.ext} type="button" onClick={() => void run(f.ext)} aria-disabled={busy !== null} aria-busy={busy === f.ext} title={f.description}
            aria-label={`Download ${f.label} for ${label}`}
            className="inline-flex h-7 items-center gap-1 rounded-md border border-slate-300 bg-white px-2 text-xs text-slate-700 hover:bg-slate-100 aria-disabled:opacity-50">
            <Download className="h-3 w-3" aria-hidden />{busy === f.ext ? "…" : f.label}
          </button>
        ))}
      </div>
      {error && <p role="alert" className="text-xs text-red-700">Export failed: {error}</p>}
    </div>
  );
}
