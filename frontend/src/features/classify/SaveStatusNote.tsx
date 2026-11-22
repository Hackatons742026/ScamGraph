import { Link } from "react-router";
import { cn } from "@/lib/utils";
import type { SaveStatus } from "./persistence";

const TONE = {
  ok: "border-emerald-200 bg-emerald-50 text-emerald-900",
  info: "border-slate-200 bg-slate-50 text-slate-800",
  warn: "border-amber-200 bg-amber-50 text-amber-900",
} as const;

const linkClass = "font-medium underline underline-offset-2";

/** Says whether the classified material was kept in live memory for later comparison. */
export function SaveStatusNote({ status }: { status: SaveStatus }) {
  const tone = status.kind === "saved" || status.kind === "saved_unverified" ? "ok" : status.kind === "analysis_only" ? "info" : "warn";
  return (
    <div role="status" className={cn("rounded-md border p-3 text-sm", TONE[tone])}>
      {status.kind === "demo" && (
        <p>
          <span className="font-medium">Demo mode: nothing was saved.</span> This result comes from synthetic data, and later uploads
          are not compared with it.
        </p>
      )}
      {status.kind === "analysis_only" && (
        <p>
          <span className="font-medium">Leave-one-out: analysis only.</span> This material was not saved, and the held-out incident is
          unchanged.
        </p>
      )}
      {status.kind === "saved" && (
        <>
          <p>
            <span className="font-medium">Saved to live memory as a new incident.</span> Later uploads are compared with it, and
            Incidents, Campaigns and the graph now include it.
          </p>
          <ul className="mt-1 flex flex-col gap-0.5">
            {status.added.map((incident) => (
              <li key={incident.id}>
                <Link to={`/incidents/${encodeURIComponent(incident.id)}`} className={linkClass}>
                  Open {incident.label}
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}
      {status.kind === "saved_unverified" && (
        <p>
          <span className="font-medium">Saved to live memory for future comparison.</span> The incident list could not be refreshed to
          show it here;{" "}
          <Link to="/incidents" className={linkClass}>
            open Incidents
          </Link>{" "}
          to check.
        </p>
      )}
      {status.kind === "not_saved" && (
        <p>
          <span className="font-medium">Not saved.</span> The incident list did not change, so the server is running without a live
          database and returned a demo answer. Later uploads are not compared with this material.
        </p>
      )}
    </div>
  );
}
