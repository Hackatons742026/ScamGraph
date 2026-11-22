import { Link } from "react-router";
import type { RunSummary } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { RUN_STATUS } from "@/lib/domain";

type StatKey = keyof Pick<
  RunSummary,
  "incidents" | "artifacts" | "campaigns" | "networks" | "unassigned" | "needs_review" | "new_candidates"
>;

const STATS: Array<{ key: StatKey; label: string; hint?: string; to?: string }> = [
  { key: "incidents", label: "Incidents", to: "/incidents" },
  { key: "artifacts", label: "Artifacts" },
  { key: "campaigns", label: "Campaigns", to: "/campaigns" },
  { key: "networks", label: "Networks", to: "/campaigns" },
  {
    key: "unassigned",
    label: "Outside campaigns",
    hint: "Not in a campaign — often New Candidate",
    to: "/incidents?status=new_candidate",
  },
  { key: "needs_review", label: "Needs review", to: "/review" },
  { key: "new_candidates", label: "New candidates", to: "/incidents?status=new_candidate" },
];

function statusVariant(status: RunSummary["status"]) {
  if (status === "done") return "success" as const;
  if (status === "failed") return "danger" as const;
  if (status === "running" || status === "pending") return "warning" as const;
  return "default" as const;
}

function formatWhen(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

export function RunSummaryCards({ run }: { run: RunSummary }) {
  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader className="flex-row items-center justify-between gap-3">
          <div>
            <CardTitle>Latest run</CardTitle>
            <p className="text-xs text-slate-500">
              {run.id} · started {formatWhen(run.started_at)}
              {run.finished_at ? ` · finished ${formatWhen(run.finished_at)}` : ""}
            </p>
          </div>
          <Badge variant={statusVariant(run.status)}>{RUN_STATUS[run.status]}</Badge>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
            {STATS.map(({ key, label, hint, to }) => {
              const value = (
                <>
                  <dt className="text-xs text-slate-500">{label}</dt>
                  <dd className="text-lg font-semibold tabular-nums text-slate-900">{run[key]}</dd>
                  {hint && <p className="mt-0.5 text-[10px] leading-tight text-slate-400">{hint}</p>}
                </>
              );
              return (
                <div key={key} className="rounded-md border border-slate-100 bg-slate-50 px-3 py-2">
                  {to ? (
                    <Link
                      to={to}
                      className="block rounded-sm outline-none ring-slate-400 hover:bg-slate-100/80 focus-visible:ring-2"
                    >
                      {value}
                    </Link>
                  ) : (
                    value
                  )}
                </div>
              );
            })}
          </dl>
          <p className="mt-3 text-xs text-slate-500">
            {run.unique_artifacts} unique · {run.duplicates} duplicates · {run.secrets_redacted} secrets redacted
          </p>
          {run.error && (
            <p role="alert" className="mt-2 text-sm text-red-700">
              Run error: {run.error}
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Artifact coverage</CardTitle>
          <p className="text-xs text-slate-500">
            Parsed vs failed counts by artifact kind for this run. Partial means parsed with gaps (for example a
            video without extracted frames).
          </p>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[28rem] text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                  <th className="py-2 pr-3 font-medium">Kind</th>
                  <th className="py-2 pr-3 font-medium">Total</th>
                  <th className="py-2 pr-3 font-medium">Parsed</th>
                  <th className="py-2 pr-3 font-medium">Partial</th>
                  <th className="py-2 font-medium">Failed</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(run.artifacts_by_kind).map(([kind, stats]) => (
                  <tr key={kind} className="border-b border-slate-100 last:border-0">
                    <td className="py-2 pr-3 font-medium text-slate-800">{kind}</td>
                    <td className="py-2 pr-3 tabular-nums">{stats.total}</td>
                    <td className="py-2 pr-3 tabular-nums text-emerald-700">{stats.parsed}</td>
                    <td className="py-2 pr-3 tabular-nums text-amber-700">{stats.partial ?? 0}</td>
                    <td className="py-2 tabular-nums text-red-700">{stats.failed}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
