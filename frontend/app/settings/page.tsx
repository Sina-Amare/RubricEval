"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { useToast } from "@/components/Toast";
import { BackLink, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import type { ProviderTestResult } from "@/lib/types";

const PRESETS = [
  "openrouter/openai/gpt-oss-120b:free",
  "openrouter/anthropic/claude-3.5-sonnet",
  "openrouter/openai/gpt-4o-mini",
  "openrouter/google/gemini-2.0-flash-001",
];

function TestPill({ r }: { r: ProviderTestResult }) {
  return (
    <span
      className={`chip ${
        r.ok ? "border-good/40 bg-good/12 text-good" : "border-bad/40 bg-bad/12 text-bad"
      }`}
      title={r.message}
    >
      {r.ok ? `Connected · ${r.latency_ms}ms` : r.message}
    </span>
  );
}

export default function SettingsPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const health = useQuery({ queryKey: ["health"], queryFn: api.health });
  const providers = useQuery({ queryKey: ["providers"], queryFn: api.listProviders });

  const [name, setName] = useState("");
  const [model, setModel] = useState(PRESETS[0]);
  const [apiKey, setApiKey] = useState("");
  const [formTest, setFormTest] = useState<ProviderTestResult | null>(null);
  const [savedTests, setSavedTests] = useState<Record<string, ProviderTestResult>>({});

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["providers"] });
    qc.invalidateQueries({ queryKey: ["health"] });
  };

  const test = useMutation({
    mutationFn: () =>
      api.testProvider({ provider: "openrouter", model_id: model.trim(), api_key: apiKey.trim() }),
    onSuccess: (r) => {
      setFormTest(r);
      toast.push({
        kind: r.ok ? "success" : "error",
        title: r.ok ? "Connection successful" : "Connection failed",
        desc: r.ok ? `${r.model_id} · ${r.latency_ms}ms` : r.message,
      });
    },
    onError: (e: any) => toast.push({ kind: "error", title: "Test failed", desc: e.message }),
  });

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
      setFormTest(null);
      refresh();
      toast.push({ kind: "success", title: "Key saved", desc: "Set as the default model." });
    },
    onError: (e: any) => toast.push({ kind: "error", title: "Couldn't save key", desc: e.message }),
  });
  const setDefault = useMutation({
    mutationFn: (id: string) => api.setDefaultProvider(id),
    onSuccess: () => {
      refresh();
      toast.push({ kind: "success", title: "Default updated" });
    },
  });
  const del = useMutation({
    mutationFn: (id: string) => api.deleteProvider(id),
    onSuccess: () => {
      refresh();
      toast.push({ kind: "info", title: "Key deleted" });
    },
  });
  const testSaved = useMutation({
    mutationFn: (id: string) => api.testSavedProvider(id),
    onSuccess: (r, id) => {
      setSavedTests((s) => ({ ...s, [id]: r }));
      toast.push({
        kind: r.ok ? "success" : "error",
        title: r.ok ? "Connection successful" : "Connection failed",
        desc: r.ok ? `${r.latency_ms}ms` : r.message,
      });
    },
  });

  const hasDefaultProvider = providers.data?.some((p) => p.is_default);
  const canTest = !!apiKey && !!model;

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
            data-testid="provider-key"
          />
        </div>
        <div className="mt-5 flex flex-wrap items-center gap-3">
          <button
            className="btn-ghost"
            onClick={() => test.mutate()}
            disabled={!canTest || test.isPending}
            data-testid="test-connection"
          >
            {test.isPending ? <Spinner /> : "Test connection"}
          </button>
          <button
            className="btn-primary"
            onClick={() => create.mutate()}
            disabled={!canTest || create.isPending}
          >
            {create.isPending ? <Spinner /> : "Save & make default"}
          </button>
          {formTest && <TestPill r={formTest} />}
        </div>
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
              <div key={p.id} className="flex flex-wrap items-center justify-between gap-3 py-3.5">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 font-medium">
                    <span className="truncate">{p.name}</span>
                    {p.is_default && (
                      <span className="chip border-good/40 bg-good/12 text-good">default</span>
                    )}
                    {savedTests[p.id] && <TestPill r={savedTests[p.id]} />}
                  </div>
                  <div className="truncate font-mono text-xs text-muted">
                    {p.model_id} · key {p.key_fingerprint}
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <button
                    className="btn-ghost"
                    onClick={() => testSaved.mutate(p.id)}
                    disabled={testSaved.isPending}
                  >
                    {testSaved.isPending && testSaved.variables === p.id ? <Spinner /> : "Test"}
                  </button>
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
