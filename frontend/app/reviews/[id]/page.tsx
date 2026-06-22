"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { EvidenceViewer } from "@/components/EvidenceViewer";
import {
  BackLink,
  DecisionBadge,
  ScoreBar,
  Spinner,
  VerdictChip,
  VerifiedBadge,
} from "@/components/ui";
import { api } from "@/lib/api";
import type { CriterionResult, Evidence } from "@/lib/types";

export default function ReportPage({ params }: { params: { id: string } }) {
  const id = params.id;
  const q = useQuery({
    queryKey: ["review", id],
    queryFn: () => api.getReview(id),
    refetchInterval: (query) => {
      const d = query.state.data;
      return d && (d.status === "completed" || d.status === "failed") ? false : 1500;
    },
  });
  const [active, setActive] = useState<Evidence | null>(null);

  if (q.isLoading || !q.data) {
    return (
      <div className="space-y-4">
        <div className="h-6 w-32 skeleton" />
        <div className="h-40 skeleton rounded-2xl" />
      </div>
    );
  }
  const r = q.data;

  if (r.status !== "completed") {
    return (
      <div className="animate-fade-up space-y-4">
        <BackLink href="/">Back</BackLink>
        <div className="card flex items-center justify-between gap-4 p-6">
          <div>
            <div className="text-sm text-muted">This review is {r.status}</div>
            {r.error_message && <div className="mt-1 text-bad">{r.error_message}</div>}
          </div>
          <Link href={`/reviews/${id}/live`} className="btn-primary">
            Watch live →
          </Link>
        </div>
      </div>
    );
  }

  const contributions: any[] = r.decision_breakdown?.contributions ?? [];

  return (
    <div className="animate-fade-up space-y-6">
      <BackLink href="/">Back to tasks</BackLink>

      {/* verdict header */}
      <div className="card overflow-hidden p-6">
        <div className="flex flex-wrap items-center justify-between gap-5">
          <div className="flex items-center gap-5">
            <DecisionBadge decision={r.decision} size="lg" />
            <div>
              <div className="text-3xl font-semibold tabular-nums">
                {r.final_score?.toFixed(0)}
                <span className="text-lg text-muted">%</span>
              </div>
              <div className="text-xs text-muted">overall score</div>
            </div>
          </div>
          <div className="text-right text-xs text-muted">
            <div className="font-mono">{r.model_id}</div>
            <div className="font-mono">
              rubric {r.rubric_content_hash.slice(0, 10)}… · {r.prompt_template_version}
            </div>
            <div className="font-mono">engine {r.engine_version}</div>
          </div>
        </div>
        {r.gate_failed && (
          <div className="mt-5 rounded-lg border border-bad/40 bg-bad/10 px-3.5 py-2.5 text-sm text-bad">
            A required gate failed — decision forced to reject.
          </div>
        )}
        {contributions.length > 0 && (
          <div className="mt-6 space-y-2.5">
            {contributions.map((c) => (
              <div key={c.key} className="flex items-center gap-3 text-sm">
                <span className="w-44 truncate text-muted">{c.key}</span>
                <div className="flex-1">
                  <ScoreBar value={c.score} />
                </div>
                <span className="w-24 text-right tabular-nums text-muted">
                  {c.score.toFixed(0)}% × {c.weight}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* criteria + evidence viewer */}
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-3">
          {[...r.results].map((res: CriterionResult) => (
            <details key={res.criterion_id} className="card group p-4" open>
              <summary className="flex cursor-pointer list-none items-center justify-between">
                <span className="flex items-center gap-2 font-medium">
                  <VerdictChip verdict={res.verdict} />
                  {res.criterion_key}
                </span>
                <span className="text-sm tabular-nums text-muted">
                  {res.score != null ? `${res.score.toFixed(0)}%` : "gate"}
                </span>
              </summary>
              {res.rationale && <p className="mt-3 text-sm leading-relaxed">{res.rationale}</p>}
              <div className="mt-3 space-y-2">
                {res.evidence.map((ev, i) => {
                  const verified = ev.verified === "verified";
                  return (
                    <button
                      key={i}
                      disabled={!verified}
                      onClick={() => setActive(ev)}
                      data-testid="evidence-item"
                      className={`w-full rounded-lg border bg-surface2 p-2.5 text-left text-xs transition ${
                        verified ? "hover:border-primary/50" : "opacity-70"
                      } ${active === ev ? "border-primary/60" : ""}`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate font-mono text-muted">
                          {ev.path}:{ev.start_line}
                          {ev.end_line !== ev.start_line ? `-${ev.end_line}` : ""}
                        </span>
                        <VerifiedBadge status={ev.verified} />
                      </div>
                      {ev.quote && (
                        <pre className="mt-1.5 overflow-x-auto font-mono text-[11px] leading-relaxed text-fg/80">
                          {ev.quote}
                        </pre>
                      )}
                    </button>
                  );
                })}
                {res.evidence.length === 0 && (
                  <div className="text-xs text-muted">No evidence cited.</div>
                )}
              </div>
            </details>
          ))}
        </div>

        <div className="lg:sticky lg:top-20 lg:self-start">
          <EvidenceViewer submissionId={r.submission_id} evidence={active} />
        </div>
      </div>
    </div>
  );
}
