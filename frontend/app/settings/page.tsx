"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { BackLink, Spinner } from "@/components/ui";
import { api } from "@/lib/api";

const PRESETS = [
  "openrouter/openai/gpt-oss-120b:free",
  "openrouter/anthropic/claude-3.5-sonnet",
  "openrouter/openai/gpt-4o-mini",
  "openrouter/google/gemini-2.0-flash-001",
];

export default function SettingsPage() {
  const qc = useQueryClient();
  const health = useQuery({ queryKey: ["health"], queryFn: api.health });
  const providers = useQuery({ queryKey: ["providers"], queryFn: api.listProviders });

  const [name, setName] = useState("");
  const [model, setModel] = useState(PRESETS[0]);
  const [apiKey, setApiKey] = useState("");
  const [err, setErr] = useState("");

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["providers"] });
    qc.invalidateQueries({ queryKey: ["health"] });
  };

  const create = useMutation({
    mutationFn: () =>
      api.createProvider({
        name: name.trim() || "OpenRouter",
        provider: "openrouter",
        model_id: model.trim(),
        api_key: apiKey.trim(),
        is_default: true,
      }),
    onSuccess: () => {
      setName("");
      setApiKey("");
      setErr("");
      refresh();
    },
    onError: (e: any) => setErr(e.message || "Failed to save"),
  });
  const setDefault = useMutation({
    mutationFn: (id: string) => api.setDefaultProvider(id),
    onSuccess: refresh,
  });
  const del = useMutation({
    mutationFn: (id: string) => api.deleteProvider(id),
    onSuccess: refresh,
  });

  const hasDefaultProvider = providers.data?.some((p) => p.is_default);

  return (
    <div className="animate-fade-up max-w-3xl space-y-6">
      <BackLink href="/">Back to tasks</BackLink>
      <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>

      <div className="card p-6">
        <div className="mb-2 text-sm font-medium">Active model</div>
        <div className="flex flex-wrap items-center gap-3">
          <span className="inline-flex items-center gap-2 rounded-lg bg-surface2 px-3 py-1.5 font-mono text-sm">
            <span className="h-2 w-2 animate-pulse rounded-full bg-good" />
            {health.data?.default_model ?? "…"}
          </span>
          <span className="chip border-border bg-surface2 text-muted">
            via {health.data?.llm_backend ?? "…"}
          </span>
        </div>
        <p className="mt-3 text-sm text-muted">
          {hasDefaultProvider
            ? "Using the default key you added below."
            : "Using the server's configured key. Add a key below to manage it from here."}
        </p>
      </div>

      <div className="card p-6">
        <div className="mb-4 text-sm font-medium">Add a model key (BYOK)</div>
        {err && (
          <div className="mb-4 rounded-lg border border-bad/40 bg-bad/10 p-2.5 text-sm text-bad">
            {err}
          </div>
        )}
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="label">Label</label>
            <input
              className="input"
              placeholder="My OpenRouter key"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div>
            <label className="label">Model</label>
            <input
              className="input font-mono text-xs"
              list="model-presets"
              value={model}
              onChange={(e) => setModel(e.target.value)}
            />
            <datalist id="model-presets">
              {PRESETS.map((m) => (
                <option key={m} value={m} />
              ))}
            </datalist>
          </div>
        </div>
        <div className="mt-4">
          <label className="label">API key — encrypted at rest, never shown again</label>
          <input
            className="input font-mono"
            type="password"
            placeholder="sk-or-v1-…"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
          />
        </div>
        <button
          className="btn-primary mt-5"
          onClick={() => create.mutate()}
          disabled={create.isPending || !apiKey || !model}
        >
          {create.isPending ? <Spinner /> : "Save & make default"}
        </button>
      </div>

      <div className="card p-6">
        <div className="mb-4 text-sm font-medium">Saved keys</div>
        {providers.isLoading ? (
          <div className="space-y-2">
            <div className="h-12 skeleton" />
            <div className="h-12 skeleton" />
          </div>
        ) : !providers.data?.length ? (
          <div className="text-sm text-muted">
            No keys saved — the server&apos;s configured key is in use.
          </div>
        ) : (
          <div className="divide-y">
            {providers.data.map((p) => (
              <div key={p.id} className="flex items-center justify-between gap-4 py-3.5">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 font-medium">
                    <span className="truncate">{p.name}</span>
                    {p.is_default && (
                      <span className="chip border-good/40 bg-good/12 text-good">default</span>
                    )}
                  </div>
                  <div className="truncate font-mono text-xs text-muted">
                    {p.model_id} · key {p.key_fingerprint}
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  {!p.is_default && (
                    <button className="btn-ghost" onClick={() => setDefault.mutate(p.id)}>
                      Make default
                    </button>
                  )}
                  <button className="btn-danger" onClick={() => del.mutate(p.id)}>
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
