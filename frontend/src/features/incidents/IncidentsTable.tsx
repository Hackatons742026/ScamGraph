import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router";
import type { CoverageLevel, IncidentStatus, IncidentSummary } from "@/api/types";
import { CoverageBadges, StatusBadge } from "@/components/domain/badges";
import { STATUS } from "@/lib/domain";
import { cn } from "@/lib/utils";

const ALL_STATUSES = Object.keys(STATUS) as IncidentStatus[];

type SortKey = "label" | "status" | "coverage" | "artifacts" | "last_seen";
type SortDir = "asc" | "desc";

const coverageRank: Record<CoverageLevel, number> = { low: 0, ok: 1 };

function compare(a: IncidentSummary, b: IncidentSummary, key: SortKey, dir: SortDir) {
  const sign = dir === "asc" ? 1 : -1;
  switch (key) {
    case "label":
      return sign * a.label.localeCompare(b.label);
    case "status":
      return sign * a.status.localeCompare(b.status);
    case "coverage":
      return sign * (coverageRank[a.coverage.level] - coverageRank[b.coverage.level]);
    case "artifacts":
      return sign * (a.artifact_count - b.artifact_count);
    case "last_seen":
      return sign * (a.last_seen ?? "").localeCompare(b.last_seen ?? "");
  }
}

function formatWhen(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString();
}

export function IncidentsTable({
  incidents,
  initialStatuses = [],
}: {
  incidents: IncidentSummary[];
  /** Pre-select status filters (e.g. from `?status=new_candidate`). */
  initialStatuses?: IncidentStatus[];
}) {
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState<Set<IncidentStatus>>(
    () => new Set(initialStatuses.filter((s) => ALL_STATUSES.includes(s))),
  );
  const [coverageFilter, setCoverageFilter] = useState<CoverageLevel | "all">("all");
  const [sortKey, setSortKey] = useState<SortKey>("last_seen");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const filtered = useMemo(() => {
    const rows = incidents.filter((i) => {
      if (statusFilter.size && !statusFilter.has(i.status)) return false;
      if (coverageFilter !== "all" && i.coverage.level !== coverageFilter) return false;
      return true;
    });
    return [...rows].sort((a, b) => compare(a, b, sortKey, sortDir));
  }, [incidents, statusFilter, coverageFilter, sortKey, sortDir]);

  function toggleStatus(status: IncidentStatus) {
    setStatusFilter((prev) => {
      const next = new Set(prev);
      if (next.has(status)) next.delete(status);
      else next.add(status);
      return next;
    });
  }

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortKey(key);
      setSortDir(key === "label" || key === "status" ? "asc" : "desc");
    }
  }

  const sortHint = (key: SortKey) => (sortKey === key ? (sortDir === "asc" ? " ↑" : " ↓") : "");

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-4">
        <fieldset className="flex flex-col gap-1.5">
          <legend className="text-xs font-medium text-slate-500">Status</legend>
          <div className="flex flex-wrap gap-1">
            {ALL_STATUSES.map((status) => {
              const active = statusFilter.has(status);
              return (
                <button
                  key={status}
                  type="button"
                  aria-pressed={active}
                  onClick={() => toggleStatus(status)}
                  className={cn(
                    "rounded-md border px-2.5 py-1 text-xs",
                    active ? "border-slate-900 bg-slate-900 text-white" : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50",
                  )}
                >
                  {STATUS[status]}
                </button>
              );
            })}
            {statusFilter.size > 0 && (
              <button type="button" className="px-2 text-xs text-slate-500 underline" onClick={() => setStatusFilter(new Set())}>
                Clear
              </button>
            )}
          </div>
        </fieldset>

        <label className="flex flex-col gap-1.5 text-xs font-medium text-slate-500">
          Coverage
          <select
            className="h-8 rounded-md border border-slate-200 bg-white px-2 text-sm font-normal text-slate-800"
            value={coverageFilter}
            onChange={(e) => setCoverageFilter(e.target.value as CoverageLevel | "all")}
          >
            <option value="all">All levels</option>
            <option value="ok">Full / ok</option>
            <option value="low">Low</option>
          </select>
        </label>
      </div>

      {filtered.length === 0 ? (
        <div className="flex items-center gap-2 rounded-md border border-dashed border-slate-300 p-6 text-sm text-slate-500">
          No incidents match these filters.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
          <table className="w-full min-w-[48rem] text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                {(
                  [
                    ["label", "Incident"],
                    ["status", "Status"],
                    ["coverage", "Coverage"],
                    ["artifacts", "Artifacts"],
                    ["last_seen", "Last seen"],
                  ] as const
                ).map(([key, label]) => (
                  <th key={key} className="px-3 py-2 font-medium">
                    <button type="button" className="hover:text-slate-800" onClick={() => toggleSort(key)}>
                      {label}
                      {sortHint(key)}
                    </button>
                  </th>
                ))}
                <th className="px-3 py-2 font-medium">Campaign</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((incident) => (
                <tr
                  key={incident.id}
                  tabIndex={0}
                  className="cursor-pointer border-b border-slate-100 last:border-0 hover:bg-slate-50 focus-visible:bg-slate-50 focus-visible:outline-none"
                  onClick={() => void navigate(`/incidents/${incident.id}`)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      void navigate(`/incidents/${incident.id}`);
                    }
                  }}
                >
                  <td className="px-3 py-2.5">
                    <Link
                      to={`/incidents/${incident.id}`}
                      className="font-medium text-slate-900 hover:underline"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {incident.label}
                    </Link>
                    {incident.reason_summary && <p className="mt-0.5 line-clamp-1 text-xs text-slate-500">{incident.reason_summary}</p>}
                  </td>
                  <td className="px-3 py-2.5">
                    <StatusBadge status={incident.status} />
                  </td>
                  <td className="px-3 py-2.5">
                    <CoverageBadges coverage={incident.coverage} />
                  </td>
                  <td className="px-3 py-2.5 tabular-nums text-slate-700">{incident.artifact_count}</td>
                  <td className="px-3 py-2.5 text-slate-600">{formatWhen(incident.last_seen)}</td>
                  <td className="px-3 py-2.5 text-slate-600">{incident.campaign_label ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
