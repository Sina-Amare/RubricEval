"use client";

import Link from "next/link";

import { BackLink, DecisionBadge, ScoreBar, Spinner, VerdictChip } from "@/components/ui";
import { useReviewStream } from "@/lib/useReviewStream";

export default function LivePage({ params }: { params: { id: string } }) {
  const id = params.id;
  const s = useReviewStream(id);
  const done = s.status === "completed" || s.status === "failed";
  const doneCount = s.order.filter((k) => s.criteria[k]?.status === "done").length;
  const pct = s.total ? Math.round((doneCount / s.total) * 100) : 0;

  return (
    <div className="animate-fade-up space-y-6">
      <BackLink href="/">Back to tasks</BackLink>

      <div className="card p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-sm text-muted">Live evaluation</div>
            <h1 className="font-mono text-lg">{id.slice(0, 12)}…</h1>
          </div>
          <div className="flex items-center gap-3">
            {!done && (
              <span className="inline-flex items-center gap-2 text-sm text-muted">
                <Spinner /> evaluating
              </span>
            )}
            <DecisionBadge decision={s.decision} size="lg" />
          </div>
        </div>
        <div className="mt-5">
          <div className="mb-1.5 flex justify-between text-xs text-muted">
            <span>
              {s.status === "connecting"
                ? "Connecting…"
                : `${doneCount} / ${s.total || "?"} criteria`}
            </span>
            <span className="font-mono">{s.modelId}</span>
          </div>
          <ScoreBar value={pct} />
        </div>
      </div>

      <div className="space-y-3">
        {s.order.length === 0 && !done && (
          <div className="space-y-3">
            <div className="h-16 skeleton rounded-2xl" />
            <div className="h-16 skeleton rounded-2xl" />
          </div>
        )}
        {s.order.map((key) => {
          const c = s.criteria[key];
          const verified = (c.evidence || []).filter((e) => e.verified === "verified").length;
          return (
            <div
              key={key}
              className="card flex items-center justify-between gap-4 p-4 animate-fade-up"
              data-testid="live-criterion"
            >
              <div className="flex min-w-0 items-center gap-3">
                {c.status === "running" ? (
                  <Spinner />
                ) : (
                  <VerdictChip verdict={c.verdict as any} />
                )}
                <div className="min-w-0">
                  <div className="truncate font-medium">{c.title || key}</div>
                  <div className="text-xs text-muted">
                    {c.status === "running"
                      ? "evaluating…"
                      : `${c.type === "gate" ? "gate" : `weight ${c.weight ?? "—"}`}${
                          c.evidence
                            ? ` · ${verified}/${c.evidence.length} evidence verified`
                            : ""
                        }`}
                  </div>
                </div>
              </div>
              {c.status === "done" && c.type === "scored" && (
                <div className="w-32 shrink-0">
                  <div className="mb-1 text-right text-xs tabular-nums text-muted">
                    {c.score?.toFixed(0)}%
                  </div>
                  <ScoreBar value={c.score ?? 0} />
                </div>
              )}
            </div>
          );
        })}
      </div>

      {done && (
        <div className="card flex flex-wrap items-center justify-between gap-4 p-6 animate-fade-up">
          <div>
            <div className="text-sm text-muted">
              {s.status === "failed" ? "Evaluation failed" : "Evaluation complete"}
            </div>
            <div className="text-xl font-semibold">
              {s.status === "failed"
                ? s.error
                : `${s.decision?.toUpperCase()} · ${s.finalScore?.toFixed(0)}%`}
            </div>
          </div>
          {s.status === "completed" && (
            <Link href={`/reviews/${id}`} className="btn-primary" data-testid="view-report">
              View full report →
            </Link>
          )}
        </div>
      )}
    </div>
  );
}
