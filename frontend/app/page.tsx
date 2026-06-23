"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { useToast } from "@/components/Toast";
import { CardSkeleton, DecisionBadge, Empty, Spinner } from "@/components/ui";
import { api } from "@/lib/api";

const STEPS = [
  ["Build a rubric", "Add weighted criteria and pass/fail gates, set thresholds, then publish a version."],
  ["Submit code", "Open a task, hit Evaluate, then paste a GitHub URL or drop a .zip."],
  ["Read the verdict", "Watch each criterion grade live — every claim links to the real code."],
];

export default function Dashboard() {
  const qc = useQueryClient();
  const router = useRouter();
  const toast = useToast();
  const [name, setName] = useState("");

  const tasks = useQuery({ queryKey: ["tasks"], queryFn: api.listTasks });
  const reviews = useQuery({ queryKey: ["reviews"], queryFn: () => api.listReviews() });

  const [confirmId, setConfirmId] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () => api.createTask(name.trim() || "Untitled task"),
    onSuccess: (t) => {
      qc.invalidateQueries({ queryKey: ["tasks"] });
      router.push(`/tasks/${t.id}/edit`);
    },
    onError: (e: any) =>
      toast.push({ kind: "error", title: "Couldn't create task", desc: e.message }),
  });
  const del = useMutation({
    mutationFn: (id: string) => api.deleteTask(id),
    onSuccess: () => {
      setConfirmId(null);
      qc.invalidateQueries({ queryKey: ["tasks"] });
      qc.invalidateQueries({ queryKey: ["reviews"] });
      toast.push({ kind: "info", title: "Task deleted" });
    },
    onError: (e: any) =>
      toast.push({ kind: "error", title: "Couldn't delete task", desc: e.message }),
  });

  return (
    <div className="animate-fade-up space-y-10">
      {/* hero */}
      <section>
        <h1 className="text-3xl font-semibold tracking-tight">Evaluation tasks</h1>
        <p className="mt-2 max-w-2xl text-[15px] text-muted">
          Define a rubric of weighted criteria and gates, then evaluate any repository
          or zip against it with transparent, evidence-backed decisions.
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate();
          }}
          className="mt-6 flex max-w-xl gap-2.5"
        >
          <input
            className="input"
            placeholder="New task name (e.g. Senior Backend Go)"
            value={name}
            onChange={(e) => setName(e.target.value)}
            data-testid="new-task-name"
          />
          <button
            className="btn-primary shrink-0"
            disabled={create.isPending}
            data-testid="create-task"
          >
            {create.isPending ? <Spinner /> : "Create task"}
          </button>
        </form>
      </section>

      {/* how it works */}
      <section className="grid gap-4 md:grid-cols-3">
        {STEPS.map(([t, d], i) => (
          <div key={t} className="card p-5">
            <div className="mb-2 flex items-center gap-2">
              <span className="grid h-6 w-6 place-items-center rounded-lg bg-primary/12 text-xs font-semibold text-primary">
                {i + 1}
              </span>
              <span className="font-medium">{t}</span>
            </div>
            <p className="text-sm text-muted">{d}</p>
          </div>
        ))}
      </section>

      {/* tasks */}
      <section>
        <div className="mb-4 flex items-baseline justify-between">
          <h2 className="text-lg font-semibold">Your tasks</h2>
          <Link href="/settings" className="text-sm text-muted hover:text-fg">
            Model & keys →
          </Link>
        </div>
        {tasks.isLoading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <CardSkeleton />
            <CardSkeleton />
            <CardSkeleton />
          </div>
        ) : !tasks.data?.length ? (
          <Empty
            title="No tasks yet"
            hint="Create your first evaluation task above to define a rubric."
            icon={
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /></svg>
            }
          />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {tasks.data.map((t) => (
              <div
                key={t.id}
                className="card card-hover flex flex-col gap-3 p-5"
                data-testid="task-card"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="font-medium leading-tight">{t.name}</div>
                  <div className="flex shrink-0 items-center gap-1.5">
                    {t.current_version_number ? (
                      <span className="chip border-border bg-surface2 text-muted">
                        v{t.current_version_number}
                      </span>
                    ) : (
                      <span className="chip border-warn/40 bg-warn/12 text-warn">draft</span>
                    )}
                    <button
                      onClick={() => setConfirmId(t.id)}
                      aria-label="Delete task"
                      data-testid="delete-task"
                      className="rounded-md p-1 text-muted transition hover:bg-bad/10 hover:text-bad"
                    >
                      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /></svg>
                    </button>
                  </div>
                </div>
                <div className="text-sm text-muted">
                  {t.draft?.criteria?.length ?? 0} criteria
                </div>
                <div className="mt-auto pt-1">
                  {confirmId === t.id ? (
                    <div className="flex items-center gap-2">
                      <span className="flex-1 text-sm text-muted">Delete this task?</span>
                      <button
                        className="btn-danger"
                        onClick={() => del.mutate(t.id)}
                        disabled={del.isPending}
                        data-testid="confirm-delete"
                      >
                        {del.isPending ? <Spinner /> : "Delete"}
                      </button>
                      <button className="btn-ghost" onClick={() => setConfirmId(null)}>
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <div className="flex gap-2">
                      <Link href={`/tasks/${t.id}/edit`} className="btn-ghost flex-1">
                        Edit rubric
                      </Link>
                      <Link href={`/tasks/${t.id}/submit`} className="btn-primary flex-1">
                        Evaluate →
                      </Link>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* recent reviews */}
      <section>
        <h2 className="mb-4 text-lg font-semibold">Recent reviews</h2>
        {reviews.isLoading ? (
          <div className="card divide-y">
            {[0, 1, 2].map((i) => (
              <div key={i} className="flex items-center justify-between px-5 py-4">
                <div className="h-5 w-40 skeleton" />
                <div className="h-4 w-24 skeleton" />
              </div>
            ))}
          </div>
        ) : !reviews.data?.length ? (
          <Empty
            title="No reviews yet"
            hint="Run a task to see evidence-backed verdicts here."
            icon={
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M9 11l3 3 8-8" /><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" /></svg>
            }
          />
        ) : (
          <div className="card divide-y overflow-hidden">
            {reviews.data.map((r) => (
              <Link
                key={r.id}
                href={r.status === "completed" ? `/reviews/${r.id}` : `/reviews/${r.id}/live`}
                className="flex items-center justify-between gap-4 px-5 py-3.5 transition hover:bg-surface2"
              >
                <div className="flex items-center gap-3">
                  <DecisionBadge decision={r.decision} />
                  <span className="font-mono text-xs text-muted">{r.id.slice(0, 8)}</span>
                </div>
                <div className="flex items-center gap-5 text-sm">
                  <span className="font-medium">
                    {r.final_score != null ? `${r.final_score.toFixed(0)}%` : "—"}
                  </span>
                  <span className="w-20 text-right capitalize text-muted">{r.status}</span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
