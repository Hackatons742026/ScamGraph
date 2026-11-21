import { Download } from "lucide-react";
import { useState } from "react";
import { ApiRequestError } from "@/api/client";
import { downloadExport, EXPORT_FORMATS, type ExportExt } from "./exports";

/** Per-campaign downloads: evidence pack (HTML), CSV and MISP. Failures show inline next to the buttons. */
export function ExportLinks({ campaignId, label }: { campaignId: string; label: string }) {
  const [busy, setBusy] = useState<ExportExt | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async (ext: ExportExt) => {
    setBusy(ext);
    setError(null);
    try {
      await downloadExport(campaignId, ext);
    } catch (e) {
      setError(e instanceof ApiRequestError ? `${e.message} (${e.status})` : "Export failed.");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="flex flex-col gap-1">
      <div className="flex flex-wrap gap-1">
        {EXPORT_FORMATS.map((f) => (
          <button key={f.ext} type="button" onClick={() => void run(f.ext)} disabled={busy !== null} title={f.description}
            aria-label={`Download ${f.label} for ${label}`}
            className="inline-flex h-7 items-center gap-1 rounded-md border border-slate-300 bg-white px-2 text-xs text-slate-700 hover:bg-slate-100 disabled:opacity-50">
            <Download className="h-3 w-3" aria-hidden />{busy === f.ext ? "…" : f.label}
          </button>
        ))}
      </div>
      {error && <p role="alert" className="text-xs text-red-700">Export failed: {error}</p>}
    </div>
  );
}
