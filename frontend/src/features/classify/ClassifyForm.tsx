import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Upload } from "lucide-react";
import { useId, useState, type FormEvent } from "react";
import {
  ApiRequestError,
  CLASSIFY_MAX_FILE_BYTES,
  CLASSIFY_MAX_UPLOAD_BYTES,
  classify,
  type ClassifyInput,
} from "@/api/client";
import type { ClassifyResult, IncidentSummary } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { USE_MOCKS } from "@/lib/env";
import { OutcomeCard } from "./OutcomeCard";
import { fetchIncidents, INCIDENTS_KEY, refreshAfterUpload, type SaveStatus } from "./persistence";
import { SaveStatusNote } from "./SaveStatusNote";

const ACCEPT =
  ".har,.html,.htm,.mhtml,.mht,image/*,video/*,.png,.jpg,.jpeg,.webp,.gif,.mp4,.webm,.mov,application/json,.json";

const MB = 1024 * 1024;

function formatLimit(bytes: number) {
  if (bytes < MB) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / MB).toFixed(bytes % MB === 0 ? 0 : 1)} MB`;
}

type Submission = { result: ClassifyResult; save: SaveStatus };

export function ClassifyForm() {
  const formId = useId();
  const client = useQueryClient();
  const [files, setFiles] = useState<File[]>([]);
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  const [excludeIncident, setExcludeIncident] = useState("");
  const [submission, setSubmission] = useState<Submission | null>(null);

  const incidents = useQuery({ queryKey: INCIDENTS_KEY, queryFn: fetchIncidents });

  const mutation = useMutation({
    mutationFn: async (input: ClassifyInput): Promise<Submission> => {
      const before = client.getQueryData<IncidentSummary[]>(INCIDENTS_KEY);
      const result = await classify(input);
      // Live mode stores a normal upload as a new incident and rebuilds the analysis before answering;
      // leave-one-out and the mock build never store anything.
      if (USE_MOCKS) return { result, save: { kind: "demo" } };
      if (input.exclude_incident) return { result, save: { kind: "analysis_only" } };
      return { result, save: await refreshAfterUpload(client, before) };
    },
    onSuccess: (data) => setSubmission(data),
  });

  const hasInput = files.length > 0 || !!text.trim() || !!url.trim();
  const totalBytes = files.reduce((sum, f) => sum + f.size, 0);
  const oversizeFile = files.some((f) => f.size > CLASSIFY_MAX_FILE_BYTES);
  const oversize = oversizeFile || totalBytes > CLASSIFY_MAX_UPLOAD_BYTES;
  const busy = mutation.isPending;

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!hasInput || busy || oversize) return;
    setSubmission(null);
    mutation.mutate({
      files,
      text: text.trim() || undefined,
      url: url.trim() || undefined,
      exclude_incident: excludeIncident || undefined,
    });
  }

  const errorMessage = oversize
    ? oversizeFile
      ? `A file is larger than ${formatLimit(CLASSIFY_MAX_FILE_BYTES)}`
      : `Upload is larger than ${formatLimit(CLASSIFY_MAX_UPLOAD_BYTES)} in total`
    : mutation.error instanceof ApiRequestError
      ? `${mutation.error.message} (${mutation.error.status})`
      : mutation.error instanceof Error
        ? mutation.error.message
        : mutation.isError
          ? "Classification failed."
          : null;

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <CardTitle>New material</CardTitle>
          <p className="text-xs text-slate-500">
            Upload HAR, page, image or video files, and/or paste text or a URL. Optional leave-one-out
            excludes an existing incident while classifying.
          </p>
          <p className="text-xs text-slate-500">
            {USE_MOCKS
              ? "Mock mode: results come from synthetic data and nothing is saved."
              : "In live mode each submission is saved as a new incident, so later uploads are compared with it. Leave-one-out only analyzes and saves nothing."}
          </p>
        </CardHeader>
        <CardContent>
          <form id={formId} className="flex flex-col gap-4" onSubmit={onSubmit}>
            <label className="flex flex-col gap-1.5 text-xs font-medium text-slate-500">
              Files
              <input
                type="file"
                multiple
                accept={ACCEPT}
                className="block w-full text-sm font-normal text-slate-800 file:mr-3 file:rounded-md file:border-0 file:bg-slate-100 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-slate-800 hover:file:bg-slate-200"
                onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
              />
              <span className="font-normal text-slate-400">
                Max {formatLimit(CLASSIFY_MAX_FILE_BYTES)} per file · {formatLimit(CLASSIFY_MAX_UPLOAD_BYTES)} total
                {files.length > 0
                  ? ` · ${files.length} selected · ${formatLimit(totalBytes)} total`
                  : ""}
              </span>
            </label>

            <label className="flex flex-col gap-1.5 text-xs font-medium text-slate-500">
              Pasted text
              <textarea
                rows={4}
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Optional note, OCR snippet, or ad copy…"
                className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-normal text-slate-800 placeholder:text-slate-400"
              />
            </label>

            <label className="flex flex-col gap-1.5 text-xs font-medium text-slate-500">
              URL
              <input
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://…"
                className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm font-normal text-slate-800 placeholder:text-slate-400"
              />
            </label>

            <label htmlFor={`${formId}-loo`} className="flex flex-col gap-1.5 text-xs font-medium text-slate-500">
              Leave one out (optional)
              <select
                id={`${formId}-loo`}
                value={excludeIncident}
                onChange={(e) => setExcludeIncident(e.target.value)}
                disabled={incidents.isPending || incidents.isError}
                className="h-9 rounded-md border border-slate-200 bg-white px-2 text-sm font-normal text-slate-800 disabled:opacity-60"
              >
                <option value="">{incidents.isPending ? "Loading incidents…" : "None"}</option>
                {(incidents.data ?? []).map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.label}
                  </option>
                ))}
              </select>
              <span className="font-normal text-slate-400">Analysis only: a leave-one-out run is never saved.</span>
              {incidents.isError && (
                <span className="font-normal text-amber-700">
                  Could not load incidents for leave-one-out. Classify still works without it.{" "}
                  <button
                    type="button"
                    className="underline"
                    onClick={() => void incidents.refetch()}
                  >
                    Retry
                  </button>
                </span>
              )}
            </label>

            <div className="flex flex-wrap items-center gap-3">
              <Button type="submit" disabled={!hasInput || busy || oversize} aria-busy={busy}>
                {busy ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <Upload className="h-4 w-4" aria-hidden />}
                {busy ? "Classifying…" : "Classify"}
              </Button>
              {!hasInput && <span className="text-xs text-slate-500">Add at least one file, text, or URL.</span>}
            </div>

            {errorMessage && (
              <div role="alert" className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">
                {errorMessage}
              </div>
            )}
          </form>
        </CardContent>
      </Card>

      {submission && (
        <>
          <SaveStatusNote status={submission.save} />
          <OutcomeCard result={submission.result} />
        </>
      )}
    </div>
  );
}
