"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useState } from "react";

import { useToast } from "@/components/Toast";
import { BackLink, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import type { CriterionIn, CriterionType, RubricDraft } from "@/lib/types";

function emptyCriterion(): CriterionIn {
  return {
    key: "",
    title: "",
    instructions: "",
    type: "scored",
    weight: 20,
    gate_policy: null,
    pass_threshold: null,
  };
}

function slug(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 60);
}

export default function EditTaskPage({ params }: { params: { id: string } }) {
  const id = params.id;
  const qc = useQueryClient();
  const toast = useToast();
  const task = useQuery({ queryKey: ["task", id], queryFn: () => api.getTask(id) });
  const [draft, setDraft] = useState<RubricDraft | null>(null);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    if (task.data && draft === null) setDraft(task.data.draft);
  }, [task.data, draft]);

  const save = useMutation({
    mutationFn: () => api.saveRubric(id, draft!),
    onSuccess: () => {
      setMsg("Draft saved");
      toast.push({ kind: "success", title: "Draft saved" });
    },
    onError: (e: any) =>
      toast.push({ kind: "error", title: "Couldn't save draft", desc: e.message }),
  });
  const publish = useMutation({
    mutationFn: async () => {
      await api.saveRubric(id, draft!);
      return api.publishRubric(id);
    },
    onSuccess: (r) => {
      setMsg(`Published v${r.version_number} · ${r.content_hash.slice(0, 10)}…`);
      qc.invalidateQueries({ queryKey: ["task", id] });
      toast.push({
        kind: "success",
        title: `Published v${r.version_number}`,
        desc: `Rubric ${r.content_hash.slice(0, 10)}… — ready to evaluate.`,
      });
    },
    onError: (e: any) => {
      setMsg(e.message || "Publish failed");
      toast.push({ kind: "error", title: "Publish failed", desc: e.message });
    },
  });

  if (task.isLoading || draft === null) {
    return (
      <div className="space-y-4">
        <div className="h-6 w-40 skeleton" />
        <div className="h-32 skeleton" />
        <div className="h-32 skeleton" />
      </div>
    );
  }

  const update = (i: number, patch: Partial<CriterionIn>) =>
    setDraft((d) =>
      d ? { ...d, criteria: d.criteria.map((c, idx) => (idx === i ? { ...c, ...patch } : c)) } : d,
    );
  const add = () =>
    setDraft((d) => (d ? { ...d, criteria: [...d.criteria, emptyCriterion()] } : d));
  const remove = (i: number) =>
    setDraft((d) => (d ? { ...d, criteria: d.criteria.filter((_, idx) => idx !== i) } : d));

  const scored = draft.criteria.filter((c) => c.type === "scored");
  const totalWeight = scored.reduce((s, c) => s + (c.weight || 0), 0) || 1;

  return (
    <div className="animate-fade-up space-y-6">
      <BackLink href="/">Back to tasks</BackLink>

      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{task.data?.name}</h1>
          <p className="mt-0.5 text-sm text-muted">
            {task.data?.current_version_number
              ? `Published v${task.data.current_version_number}`
              : "Unpublished draft"}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
          {msg && <span className="w-full text-sm text-muted sm:w-auto">{msg}</span>}
          <button className="btn-ghost" onClick={() => save.mutate()} disabled={save.isPending}>
            {save.isPending ? <Spinner /> : "Save draft"}
          </button>
          <button
            className="btn-ghost"
            onClick={() => publish.mutate()}
            disabled={publish.isPending}
            data-testid="publish"
          >
            {publish.isPending ? <Spinner /> : "Publish version"}
          </button>
          <Link href={`/tasks/${id}/submit`} className="btn-primary">
            Evaluate →
          </Link>
        </div>
      </div>

      {!task.data?.current_version_number && (
        <div className="rounded-xl border border-warn/30 bg-warn/8 p-3.5 text-sm text-warn">
          Add your criteria, then <b>Publish version</b> before evaluating — reviews always
          run against a published rubric snapshot.
        </div>
      )}

      <div className="space-y-4">
        {draft.criteria.map((c, i) => (
          <div key={i} className="card p-5" data-testid="criterion-row">
            <div className="flex flex-wrap items-center gap-3">
              <input
                className="input w-full sm:w-auto sm:min-w-[200px] sm:flex-1"
                placeholder="Criterion title (e.g. Has automated tests)"
                value={c.title}
                onChange={(e) =>
                  update(i, { title: e.target.value, key: c.key || slug(e.target.value) })
                }
              />
              <select
                className="input w-36"
                value={c.type}
                onChange={(e) => {
                  const type = e.target.value as CriterionType;
                  update(i, {
                    type,
                    gate_policy: type === "gate" ? c.gate_policy ?? "must_pass" : null,
                    weight: type === "scored" ? c.weight || 20 : 0,
                  });
                }}
              >
                <option value="scored">Scored</option>
                <option value="gate">Gate</option>
              </select>
              {c.type === "gate" ? (
                <select
                  className="input w-40"
                  value={c.gate_policy ?? "must_pass"}
                  onChange={(e) => update(i, { gate_policy: e.target.value as any })}
                >
                  <option value="must_pass">Must pass</option>
                  <option value="force_reject">Force reject</option>
                </select>
              ) : (
                <div className="flex w-44 items-center gap-2">
                  <input
                    type="range"
                    min={1}
                    max={100}
                    value={c.weight}
                    onChange={(e) => update(i, { weight: Number(e.target.value) })}
                    style={{ accentColor: "rgb(var(--primary))" }}
                    className="flex-1"
                  />
                  <span className="w-9 text-right text-sm tabular-nums text-muted">{c.weight}</span>
                </div>
              )}
              <button
                onClick={() => remove(i)}
                className="rounded-lg border px-3 py-2.5 text-sm text-muted transition hover:border-bad/40 hover:text-bad"
                aria-label="Remove criterion"
              >
                Remove
              </button>
            </div>
            <textarea
              className="input mt-3 min-h-[68px] resize-y"
              placeholder="Instructions for the grader — what to look for. Wrap key signals in `backticks`."
              value={c.instructions}
              onChange={(e) => update(i, { instructions: e.target.value })}
            />
            {c.type === "scored" && (
              <div className="mt-2 text-xs text-muted">
                Contributes {(((c.weight || 0) / totalWeight) * 100).toFixed(0)}% of the score
              </div>
            )}
          </div>
        ))}
        <button
          className="btn-ghost w-full border-dashed py-3"
          onClick={add}
          data-testid="add-criterion"
        >
          + Add criterion
        </button>
      </div>

      <div className="card p-5">
        <div className="mb-3 font-medium">Decision thresholds</div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="label">Accept at ≥ (score)</label>
            <input
              type="number"
              className="input"
              value={draft.decision_config.accept_at}
              onChange={(e) =>
                setDraft((d) =>
                  d
                    ? { ...d, decision_config: { ...d.decision_config, accept_at: Number(e.target.value) } }
                    : d,
                )
              }
            />
          </div>
          <div>
            <label className="label">Review at ≥ (score)</label>
            <input
              type="number"
              className="input"
              value={draft.decision_config.review_at}
              onChange={(e) =>
                setDraft((d) =>
                  d
                    ? { ...d, decision_config: { ...d.decision_config, review_at: Number(e.target.value) } }
                    : d,
                )
              }
            />
          </div>
        </div>
        <p className="mt-3 text-xs text-muted">
          Below the review threshold → reject. Any failed gate forces reject regardless of score.
        </p>
      </div>
    </div>
  );
}
