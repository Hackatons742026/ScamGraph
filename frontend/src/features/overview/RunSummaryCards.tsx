import type { RunSummary } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { RUN_STATUS } from "@/lib/domain";

const STATS: Array<{ key: keyof Pick<RunSummary, "incidents" | "artifacts" | "campaigns" | "networks" | "unassigned" | "needs_review" | "new_candidates">; label: string }> = [
  { key: "incidents", label: "Incidents" },
  { key: "artifacts", label: "Artifacts" },
  { key: "campaigns", label: "Campaigns" },
  { key: "networks", label: "Networks" },
  { key: "unassigned", label: "Unassigned" },
  { key: "needs_review", label: "Needs review" },
  { key: "new_candidates", label: "New candidates" },
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
            {STATS.map(({ key, label }) => (
              <div key={key} className="rounded-md border border-slate-100 bg-slate-50 px-3 py-2">
                <dt className="text-xs text-slate-500">{label}</dt>
                <dd className="text-lg font-semibold tabular-nums text-slate-900">{run[key]}</dd>
              </div>
            ))}
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
          <p className="text-xs text-slate-500">Parsed vs failed counts by artifact kind for this run.</p>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[28rem] text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                  <th className="py-2 pr-3 font-medium">Kind</th>
                  <th className="py-2 pr-3 font-medium">Total</th>
                  <th className="py-2 pr-3 font-medium">Parsed</th>
                  <th className="py-2 font-medium">Failed</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(run.artifacts_by_kind).map(([kind, stats]) => (
                  <tr key={kind} className="border-b border-slate-100 last:border-0">
                    <td className="py-2 pr-3 font-medium text-slate-800">{kind}</td>
                    <td className="py-2 pr-3 tabular-nums">{stats.total}</td>
                    <td className="py-2 pr-3 tabular-nums text-emerald-700">{stats.parsed}</td>
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
