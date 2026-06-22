"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { BackLink, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import type { Submission } from "@/lib/types";

export default function SubmitPage({ params }: { params: { id: string } }) {
  const id = params.id;
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [drag, setDrag] = useState(false);
  const [sub, setSub] = useState<Submission | null>(null);
  const [err, setErr] = useState("");

  const ingest = useMutation({
    mutationFn: () => (file ? api.submitZip(file) : api.submitGithub(url.trim())),
    onSuccess: (s) => {
      setSub(s);
      setErr("");
    },
    onError: (e: any) => setErr(e.message || "Ingestion failed"),
  });
  const run = useMutation({
    mutationFn: () => api.createReview(id, sub!.id),
    onSuccess: (r) => router.push(`/reviews/${r.id}/live`),
    onError: (e: any) => setErr(e.message || "Could not start review"),
  });

  return (
    <div className="animate-fade-up max-w-3xl space-y-6">
      <BackLink href="/">Back to tasks</BackLink>
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Evaluate a submission</h1>
        <p className="mt-1 text-sm text-muted">
          Provide a GitHub repository or a .zip — we fetch the files, then grade them
          against this task&apos;s published rubric.
        </p>
      </div>

      {err && (
        <div
          className="rounded-xl border border-bad/40 bg-bad/10 p-3 text-sm text-bad"
          data-testid="submit-error"
        >
          {err}
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        {/* GitHub */}
        <div className={`card p-5 transition ${url ? "border-primary/40" : ""}`}>
          <div className="mb-3 flex items-center gap-2 font-medium">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2A10 10 0 0 0 8.8 21.5c.5.1.7-.2.7-.5v-1.7c-2.8.6-3.4-1.3-3.4-1.3-.5-1.1-1.1-1.4-1.1-1.4-.9-.6.1-.6.1-.6 1 .1 1.5 1 1.5 1 .9 1.5 2.3 1.1 2.9.8.1-.6.3-1.1.6-1.3-2.2-.300-4.6-1.1-4.6-5 0-1.1.4-2 1-2.7-.1-.3-.4-1.3.1-2.7 0 0 .8-.3 2.7 1a9.4 9.4 0 0 1 5 0c1.9-1.3 2.7-1 2.7-1 .5 1.4.2 2.4.1 2.7.6.7 1 1.6 1 2.7 0 3.9-2.3 4.7-4.6 5 .4.3.7.9.7 1.9v2.8c0 .3.2.6.7.5A10 10 0 0 0 12 2z" /></svg>
            From GitHub
          </div>
          <label className="label">Repository URL</label>
          <input
            className="input"
            placeholder="https://github.com/user/repo"
            value={url}
            onChange={(e) => {
              setUrl(e.target.value);
              setFile(null);
            }}
            data-testid="github-url"
          />
          <p className="mt-2 text-xs text-muted">Public repositories, shallow-cloned.</p>
        </div>

        {/* ZIP */}
        <div className={`card p-5 transition ${file ? "border-primary/40" : ""}`}>
          <div className="mb-3 flex items-center gap-2 font-medium">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3" /></svg>
            From a ZIP
          </div>
          <label
            onDragOver={(e) => {
              e.preventDefault();
              setDrag(true);
            }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDrag(false);
              const f = e.dataTransfer.files?.[0];
              if (f) {
                setFile(f);
                setUrl("");
              }
            }}
            className={`flex h-[92px] cursor-pointer flex-col items-center justify-center gap-1 rounded-xl border border-dashed text-sm transition ${
              drag ? "border-primary bg-primary/5" : "border-border bg-surface2"
            }`}
          >
            {file ? (
              <span className="font-medium">{file.name}</span>
            ) : (
              <>
                <span className="text-muted">Drop a .zip here, or click to browse</span>
              </>
            )}
            <input
              type="file"
              accept=".zip,application/zip"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0] || null;
                setFile(f);
                if (f) setUrl("");
              }}
              data-testid="zip-input"
            />
          </label>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <button
          className="btn-ghost"
          onClick={() => ingest.mutate()}
          disabled={ingest.isPending || (!url && !file)}
          data-testid="ingest"
        >
          {ingest.isPending ? <Spinner /> : "Load files"}
        </button>
        <button
          className="btn-primary"
          onClick={() => run.mutate()}
          disabled={!sub || run.isPending}
          data-testid="start-review"
        >
          {run.isPending ? <Spinner /> : "Start evaluation →"}
        </button>
        {!sub && (
          <span className="text-xs text-muted">Load files first, then start.</span>
        )}
      </div>

      {sub && (
        <div className="card animate-fade-up p-5" data-testid="submission-summary">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div className="truncate font-medium">{sub.source_ref}</div>
            <span className="chip border-border bg-surface2 text-muted">
              {sub.file_count} files · {(sub.total_bytes / 1024).toFixed(0)} KB
            </span>
          </div>
          <div className="max-h-60 overflow-auto rounded-lg border bg-surface2 p-3 font-mono text-xs text-muted">
            {sub.files.map((f) => (
              <div key={f.path} className="flex justify-between gap-4 py-0.5">
                <span className="truncate">{f.path}</span>
                <span className="shrink-0">{f.line_count} ln</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
