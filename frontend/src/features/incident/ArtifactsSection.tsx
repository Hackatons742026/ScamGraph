import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, unwrap } from "@/api/client";
import type { ArtifactSummary } from "@/api/types";
import { QueryState } from "@/components/domain/QueryState";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { MediaGallery } from "./MediaGallery";

function parseVariant(status: ArtifactSummary["parse_status"]) {
  if (status === "failed") return "danger" as const;
  if (status === "partial") return "warning" as const;
  if (status === "skipped") return "outline" as const;
  return "success" as const;
}

function ArtifactDetailPanel({ id }: { id: string }) {
  const detail = useQuery({
    queryKey: ["artifacts", id],
    queryFn: () => unwrap(api.GET("/api/artifacts/{artifact_id}", { params: { path: { artifact_id: id } } })),
  });

  return (
    <QueryState query={detail}>
      {(art) => (
        <div className="mt-3 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm">
          <p className="font-medium text-slate-900">{art.name_display}</p>
          <p className="mt-1 text-xs text-slate-500">
            {art.kind}
            {art.role ? ` · ${art.role}` : ""}
            {art.funnel_step != null ? ` · funnel step ${art.funnel_step}` : ""}
            {art.captured_at ? ` · captured ${new Date(art.captured_at).toLocaleString()}` : ""}
          </p>
          {art.error && <p className="mt-2 text-sm text-red-700">Parse error: {art.error}</p>}
          {art.duplicate_of && (
            <p className="mt-1 text-xs text-slate-500">
              Duplicate of <span className="font-mono">{art.duplicate_of}</span>
            </p>
          )}
          {art.hosts_display.length > 0 && (
            <p className="mt-2 text-xs text-slate-600">Hosts: {art.hosts_display.join(", ")}</p>
          )}
          {art.request_count > 0 && <p className="text-xs text-slate-600">{art.request_count} requests</p>}
          {art.pages.length > 0 && (
            <ul className="mt-2 space-y-1 text-xs text-slate-600">
              {art.pages.map((p) => (
                <li key={p.url_display}>
                  {p.title ?? "Untitled"} · {p.domain_display} · <span className="font-mono">{p.url_display}</span>
                </li>
              ))}
            </ul>
          )}
          {art.redirect_chain.length > 0 && (
            <ol className="mt-2 list-decimal space-y-1 pl-4 text-xs text-slate-600">
              {art.redirect_chain.map((h) => (
                <li key={h.seq}>
                  <span className="font-mono">{h.url_display}</span>
                  {h.status != null ? ` (${h.status})` : ""} · {h.kind}
                </li>
              ))}
            </ol>
          )}
          {art.ocr_text && <p className="mt-2 text-xs text-slate-600">OCR: {art.ocr_text}</p>}
          <MediaGallery media={art.media} />
        </div>
      )}
    </QueryState>
  );
}

export function ArtifactsSection({ artifacts }: { artifacts: ArtifactSummary[] }) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const failed = artifacts.filter((a) => a.parse_status === "failed");

  return (
    <Card>
      <CardHeader>
        <CardTitle>Artifacts</CardTitle>
        <p className="text-xs text-slate-500">Select an artifact to load GET /api/artifacts/{"{id}"} detail.</p>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {failed.length > 0 && (
          <div role="status" className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">
            <p className="font-medium">{failed.length} failed artifact{failed.length === 1 ? "" : "s"}</p>
            <ul className="mt-1 list-disc pl-5">
              {failed.map((a) => (
                <li key={a.id}>
                  <span className="font-medium">{a.name_display}</span>
                  {a.error ? ` — ${a.error}` : ""}
                </li>
              ))}
            </ul>
          </div>
        )}

        {artifacts.length === 0 ? (
          <p className="text-sm text-slate-500">No artifacts on this incident.</p>
        ) : (
          <ul className="divide-y divide-slate-100 rounded-md border border-slate-200">
            {artifacts.map((a) => {
              const active = selectedId === a.id;
              return (
                <li key={a.id}>
                  <button
                    type="button"
                    aria-pressed={active}
                    onClick={() => setSelectedId((cur) => (cur === a.id ? null : a.id))}
                    className={cn(
                      "flex w-full flex-wrap items-center justify-between gap-2 px-3 py-2.5 text-left text-sm hover:bg-slate-50",
                      active && "bg-slate-50",
                    )}
                  >
                    <span className="font-medium text-slate-900">{a.name_display}</span>
                    <span className="flex flex-wrap items-center gap-2">
                      <Badge variant="outline">{a.kind}</Badge>
                      <Badge variant={parseVariant(a.parse_status)}>{a.parse_status}</Badge>
                      {a.funnel_step != null && <span className="text-xs text-slate-500">step {a.funnel_step}</span>}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}

        {selectedId && <ArtifactDetailPanel id={selectedId} />}
      </CardContent>
    </Card>
  );
}
