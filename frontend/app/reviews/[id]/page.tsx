"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useState } from "react";

import { EvidenceViewer } from "@/components/EvidenceViewer";
import {
  BackLink,
  DecisionBadge,
  ErrorCard,
  ScoreBar,
  VerdictChip,
  VerifiedBadge,
} from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import type { CriterionResult, Evidence } from "@/lib/types";

interface Contribution {
  key: string;
  score: number;
  weight: number;
}

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

  // Auto-open the first verified evidence so the viewer isn't empty.
  useEffect(() => {
    if (active || !q.data) return;
    for (const res of q.data.results || []) {
      const v = res.evidence.find((e) => e.verified === "verified");
      if (v) {
        setActive(v);
        break;
      }
    }
  }, [q.data, active]);

  if (q.isError) {
    return (
      <div className="animate-fade-up space-y-4">
        <BackLink href="/">Back to tasks</BackLink>
        <ErrorCard
          title="Couldn't load this review"
          message={errorMessage(q.error)}
          onRetry={() => q.refetch()}
        />
      </div>
    );
  }

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
    const failed = r.status === "failed";
    return (
      <div className="animate-fade-up space-y-4">
        <BackLink href="/">Back to tasks</BackLink>
        <div className="card flex flex-wrap items-center justify-between gap-4 p-6">
          <div className="min-w-0">
            <div className="text-sm text-muted">
              {failed ? "This evaluation failed" : `This review is ${r.status}`}
            </div>
            {failed && r.error_message ? (
              <div className="mt-1 break-words text-bad">{r.error_message}</div>
            ) : (
              !failed && (
                <div className="mt-1 text-fg">It’s still running — follow it live.</div>
              )
            )}
          </div>
          {!failed && (
            <Link href={`/reviews/${id}/live`} className="btn-primary">
              Watch live →
            </Link>
          )}
        </div>
      </div>
    );
  }

  const contributions = (r.decision_breakdown?.contributions ?? []) as Contribution[];

  return (
    <div className="animate-fade-up space-y-6">
      <BackLink href="/">Back to tasks</BackLink>

      {/* verdict header */}
      <div className="card overflow-hidden p-6">
        <div className="flex flex-wrap items-start justify-between gap-5">
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
          <div className="min-w-0 max-w-full break-all text-left font-mono text-xs leading-relaxed text-muted sm:text-right">
            <div>{r.model_id}</div>
            <div>
              rubric {r.rubric_content_hash.slice(0, 10)}… · {r.prompt_template_version}
            </div>
            <div>engine {r.engine_version}</div>
          </div>
        </div>
        {r.gate_failed && (
          <div
            className="mt-5 rounded-lg border border-bad/40 bg-bad/10 px-3.5 py-2.5 text-sm text-bad"
            role="alert"
          >
            A required gate failed — decision forced to reject.
          </div>
        )}
        {contributions.length > 0 && (
          <div className="mt-6 space-y-2.5">
            {contributions.map((c) => (
              <div key={c.key} className="flex items-center gap-3 text-sm">
                <span className="w-28 shrink-0 break-words font-mono text-xs text-muted sm:w-48 sm:text-sm">
                  {c.key}
                </span>
                <div className="flex-1">
                  <ScoreBar value={c.score} />
                </div>
                <span className="w-20 whitespace-nowrap text-right tabular-nums text-muted sm:w-24">
                  {c.score.toFixed(0)}% × {c.weight}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* criteria + evidence viewer */}
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="order-first self-start sticky top-16 z-10 lg:order-last lg:top-20">
          <EvidenceViewer submissionId={r.submission_id} evidence={active} />
        </div>

        <div className="space-y-3">
          {[...r.results].map((res: CriterionResult) => (
            <details key={res.criterion_id} className="card group p-4" open>
              <summary className="focus-ring flex cursor-pointer list-none items-center justify-between gap-3 rounded-md">
                <span className="flex min-w-0 items-center gap-2 font-medium">
                  <VerdictChip verdict={res.verdict} />
                  <span className="break-words">{res.criterion_key}</span>
                </span>
                <span className="shrink-0 text-sm tabular-nums text-muted">
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
                      type="button"
                      disabled={!verified}
                      onClick={() => setActive(ev)}
                      data-testid="evidence-item"
                      className={`focus-ring w-full rounded-lg border bg-surface2 p-2.5 text-left text-xs transition ${
                        verified ? "hover:border-primary/50" : "cursor-not-allowed opacity-70"
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
      </div>
    </div>
  );
}
