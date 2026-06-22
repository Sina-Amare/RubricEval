import Link from "next/link";

import type { Decision, EvidenceVerified, Verdict } from "@/lib/types";

export function DecisionBadge({
  decision,
  size = "sm",
}: {
  decision: Decision | null | undefined;
  size?: "sm" | "lg";
}) {
  const map: Record<string, string> = {
    accept: "border-good/40 bg-good/12 text-good",
    review: "border-warn/40 bg-warn/12 text-warn",
    reject: "border-bad/40 bg-bad/12 text-bad",
  };
  const label = decision ? decision.toUpperCase() : "—";
  const cls = decision ? map[decision] : "border-border bg-surface2 text-muted";
  const pad = size === "lg" ? "px-3.5 py-1.5 text-sm" : "px-2.5 py-1 text-xs";
  return <span className={`chip font-semibold ${cls} ${pad}`}>{label}</span>;
}

export function VerdictChip({ verdict }: { verdict: Verdict | undefined }) {
  const map: Record<string, string> = {
    pass: "border-good/40 bg-good/12 text-good",
    partial: "border-warn/40 bg-warn/12 text-warn",
    fail: "border-bad/40 bg-bad/12 text-bad",
    error: "border-border bg-surface2 text-muted",
  };
  const cls = verdict ? map[verdict] : "border-border bg-surface2 text-muted";
  return <span className={`chip ${cls}`}>{verdict ?? "…"}</span>;
}

export function VerifiedBadge({ status }: { status: EvidenceVerified }) {
  if (status === "verified") {
    return (
      <span className="chip border-good/40 bg-good/12 text-good">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M20 6 9 17l-5-5" /></svg>
        verified
      </span>
    );
  }
  return (
    <span className="chip border-warn/40 bg-warn/12 text-warn" title={status}>
      unverified
    </span>
  );
}

export function ScoreBar({ value }: { value: number }) {
  const pct = Math.max(0, Math.min(100, value));
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-surface2">
      <div
        className="h-full rounded-full bg-gradient-to-r from-primary to-accent2 transition-[width] duration-500"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

export function Spinner({ className = "" }: { className?: string }) {
  return (
    <span
      className={`inline-block h-4 w-4 animate-spin rounded-full border-2 border-primary/25 border-t-primary ${className}`}
    />
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} />;
}

export function CardSkeleton() {
  return (
    <div className="card space-y-3 p-5">
      <Skeleton className="h-4 w-2/3" />
      <Skeleton className="h-3 w-1/3" />
      <div className="flex gap-2 pt-2">
        <Skeleton className="h-9 flex-1" />
        <Skeleton className="h-9 flex-1" />
      </div>
    </div>
  );
}

export function Empty({
  title,
  hint,
  icon,
}: {
  title: string;
  hint?: string;
  icon?: React.ReactNode;
}) {
  return (
    <div className="card flex flex-col items-center justify-center gap-2 p-14 text-center">
      {icon && <div className="mb-1 text-muted">{icon}</div>}
      <div className="text-base font-medium">{title}</div>
      {hint && <div className="max-w-sm text-sm text-muted">{hint}</div>}
    </div>
  );
}

export function BackLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      className="inline-flex items-center gap-1.5 text-sm text-muted transition hover:text-fg"
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m15 18-6-6 6-6" /></svg>
      {children}
    </Link>
  );
}
