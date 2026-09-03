"use client";

import { cn } from "@/lib/utils";
import { useBackendHealth } from "@/hooks/use-backend-health";

const DOT_STYLES: Record<"checking" | "online" | "offline", string> = {
  checking: "bg-muted-foreground animate-pulse",
  online: "bg-primary",
  offline: "bg-destructive",
};

const LABELS: Record<"checking" | "online" | "offline", string> = {
  checking: "Checking API…",
  online: "API Online",
  offline: "API Offline",
};

export function BackendStatus() {
  const { state, data, checkedAt } = useBackendHealth();

  return (
    <div className="flex items-center justify-between gap-6 rounded-lg border border-border bg-card px-5 py-4">
      <div className="flex items-center gap-3">
        <span
          aria-hidden
          className={cn("size-2.5 rounded-full", DOT_STYLES[state])}
        />
        <div>
          <p className="text-sm font-medium">{LABELS[state]}</p>
          <p className="text-xs text-muted-foreground">
            FastAPI · /api/v1/health
          </p>
        </div>
      </div>
      <div className="text-right text-xs text-muted-foreground">
        {data ? (
          <>
            <p>
              v{data.version} · {data.environment}
            </p>
            <p>checked {checkedAt?.toLocaleTimeString()}</p>
          </>
        ) : (
          <p>waiting for first check…</p>
        )}
      </div>
    </div>
  );
}
