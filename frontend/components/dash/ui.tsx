"use client";

/** Small shared dashboard primitives (status/score visuals). */

import { cn } from "@/lib/utils";
import type { LeadStatus } from "@/types/api";

export const LEAD_STATUSES: LeadStatus[] = [
  "NEW",
  "CONTACTED",
  "QUALIFIED",
  "CONVERTED",
  "LOST",
];

const STATUS_STYLES: Record<LeadStatus, string> = {
  NEW: "border-accent/40 bg-accent/10 text-accent",
  CONTACTED: "border-border bg-muted text-foreground",
  QUALIFIED: "border-primary/40 bg-primary/10 text-primary",
  CONVERTED: "border-emerald-500/40 bg-emerald-500/10 text-emerald-400",
  LOST: "border-destructive/40 bg-destructive/10 text-destructive",
};

export function StatusBadge({ status }: { status: LeadStatus }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold tracking-wide",
        STATUS_STYLES[status],
      )}
    >
      {status}
    </span>
  );
}

export function temperature(score: number | null): {
  label: string;
  className: string;
} {
  if (score === null) return { label: "UNSCORED", className: "bg-muted" };
  if (score >= 80) return { label: "HOT", className: "bg-primary" };
  if (score >= 50) return { label: "WARM", className: "bg-accent" };
  return { label: "COLD", className: "bg-muted-foreground" };
}

export function ScoreBar({ score }: { score: number | null }) {
  const t = temperature(score);
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-muted">
        <div
          className={cn("h-full rounded-full", t.className)}
          style={{ width: `${score ?? 0}%` }}
        />
      </div>
      <span className="w-10 text-right font-mono text-xs text-muted-foreground">
        {score ?? "—"}
      </span>
      <span className="text-[10px] font-semibold text-muted-foreground">{t.label}</span>
    </div>
  );
}

export function formatPkr(amount: number): string {
  if (amount >= 10_000_000) return `PKR ${(amount / 10_000_000).toFixed(2)} cr`;
  if (amount >= 100_000) return `PKR ${(amount / 100_000).toFixed(1)} lac`;
  return `PKR ${amount.toLocaleString()}`;
}

export function formatBudget(min: number | null, max: number | null): string {
  if (min && max) return `${formatPkr(min)} – ${formatPkr(max)}`;
  if (max) return `up to ${formatPkr(max)}`;
  if (min) return `from ${formatPkr(min)}`;
  return "—";
}

export function timeAgo(iso: string): string {
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = seconds / 60;
  if (minutes < 60) return `${Math.floor(minutes)}m ago`;
  const hours = minutes / 60;
  if (hours < 24) return `${Math.floor(hours)}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}
