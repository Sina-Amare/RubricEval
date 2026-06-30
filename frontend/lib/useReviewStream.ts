"use client";

import { useEffect, useRef, useState } from "react";

import { streamUrl } from "./api";
import type { Decision } from "./types";

export interface LiveCriterion {
  key: string;
  title?: string;
  index: number;
  status: "running" | "done";
  verdict?: string;
  score?: number | null;
  confidence?: number;
  type?: string;
  weight?: number;
  evidence?: { verified: string }[];
}

export interface LiveState {
  status: "connecting" | "running" | "completed" | "failed";
  total: number;
  modelId?: string;
  criteria: Record<string, LiveCriterion>;
  order: string[];
  decision?: Decision;
  finalScore?: number;
  gateFailed?: boolean;
  error?: string;
}

const TERMINAL = new Set(["review_completed", "review_failed"]);
const EVENT_TYPES = [
  "review_started",
  "criterion_started",
  "criterion_completed",
  "evidence_verified",
  "decision_computed",
  "review_completed",
  "review_failed",
];

function reduce(prev: LiveState, type: string, p: any): LiveState {
  switch (type) {
    case "review_started":
      return { ...prev, status: "running", total: p.total_criteria, modelId: p.model_id };
    case "criterion_started": {
      const criteria = { ...prev.criteria };
      criteria[p.key] = { key: p.key, title: p.title, index: p.index, status: "running" };
      const order = prev.order.includes(p.key) ? prev.order : [...prev.order, p.key];
      return { ...prev, criteria, order };
    }
    case "criterion_completed": {
      const criteria = { ...prev.criteria };
      const existing = criteria[p.key] || { key: p.key, index: prev.order.length };
      criteria[p.key] = {
        ...existing,
        status: "done",
        verdict: p.result.verdict,
        score: p.result.score,
        confidence: p.result.confidence,
        type: p.result.type,
        weight: p.result.weight,
        evidence: p.evidence,
      };
      const order = prev.order.includes(p.key) ? prev.order : [...prev.order, p.key];
      return { ...prev, criteria, order };
    }
    case "decision_computed":
      return {
        ...prev,
        decision: p.decision,
        finalScore: p.final_score,
        gateFailed: p.gate_failed,
      };
    case "review_completed":
      return { ...prev, status: "completed", decision: p.decision, finalScore: p.final_score };
    case "review_failed":
      return { ...prev, status: "failed", error: p.error };
    default:
      return prev;
  }
}

export function useReviewStream(reviewId: string): LiveState {
  const [state, setState] = useState<LiveState>({
    status: "connecting",
    total: 0,
    criteria: {},
    order: [],
  });
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const es = new EventSource(streamUrl(reviewId));
    esRef.current = es;
    let opened = false;

    // Fail only if the stream never OPENS (bad token / API down). A stream that
    // has opened but is still queued behind the worker is healthy — the backend
    // sends keep-alive SSE comments that fire no event, so "no event yet" must
    // NOT be treated as a failure.
    const connectTimer = setTimeout(() => {
      if (!opened) {
        setState((prev) =>
          prev.status === "connecting"
            ? {
                ...prev,
                status: "failed",
                error:
                  "Couldn't reach the evaluation stream. Check that the API is running and that you're signed in.",
              }
            : prev,
        );
      }
    }, 8000);

    // A successful SSE handshake proves liveness even before the first event.
    es.onopen = () => {
      opened = true;
      clearTimeout(connectTimer);
    };

    const handler = (type: string) => (e: MessageEvent) => {
      opened = true;
      let payload: any = {};
      try {
        payload = JSON.parse(e.data);
      } catch {
        return;
      }
      setState((prev) => reduce(prev, type, payload));
      if (TERMINAL.has(type)) {
        clearTimeout(connectTimer);
        es.close();
      }
    };
    EVENT_TYPES.forEach((t) => es.addEventListener(t, handler(t)));

    es.onerror = () => {
      // The browser auto-reconnects on transient blips (readyState CONNECTING);
      // only a CLOSED stream is a terminal failure worth surfacing.
      if (es.readyState === EventSource.CLOSED) {
        clearTimeout(connectTimer);
        setState((prev) =>
          prev.status === "completed"
            ? prev
            : {
                ...prev,
                status: "failed",
                error: prev.error || "The evaluation stream was interrupted.",
              },
        );
      }
    };

    return () => {
      clearTimeout(connectTimer);
      es.close();
    };
  }, [reviewId]);

  return state;
}
