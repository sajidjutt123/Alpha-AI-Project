"use client";

import { useEffect, useState } from "react";
import { Activity, Flame, Home, TrendingUp } from "lucide-react";

import { analyticsApi } from "@/lib/api";
import type { AnalyticsOverview } from "@/types/api";
import { LEAD_STATUSES } from "@/components/dash/ui";

function Kpi({
  label,
  value,
  sub,
  icon,
  accent,
}: {
  label: string;
  value: string;
  sub: string;
  icon: React.ReactNode;
  accent: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {label}
          </p>
          <p className="mt-2 text-3xl font-semibold tracking-tight">{value}</p>
          <p className="mt-1 text-xs text-muted-foreground">{sub}</p>
        </div>
        <div className={`rounded-lg p-2 ${accent}`}>{icon}</div>
      </div>
    </div>
  );
}

export function KpiCards() {
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    analyticsApi
      .overview()
      .then(setOverview)
      .catch(() => setError(true));
  }, []);

  if (error) {
    return (
      <p className="rounded-xl border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
        Failed to load analytics.
      </p>
    );
  }
  if (!overview) {
    return (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="h-32 animate-pulse rounded-xl border border-border bg-card" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi
          label="Total Leads"
          value={String(overview.total_leads)}
          sub={`${overview.new_leads_7d} new in last 7 days`}
          icon={<Activity className="size-5 text-accent-foreground" />}
          accent="bg-accent/20"
        />
        <Kpi
          label="Hot Leads"
          value={String(overview.hot_leads)}
          sub={`${overview.warm_leads} warm · ${overview.cold_leads} cold`}
          icon={<Flame className="size-5 text-primary-foreground" />}
          accent="bg-primary/20"
        />
        <Kpi
          label="Conversion"
          value={`${(overview.conversion_rate * 100).toFixed(1)}%`}
          sub={`avg score ${overview.avg_qualification_score?.toFixed(0) ?? "—"}`}
          icon={<TrendingUp className="size-5 text-emerald-300" />}
          accent="bg-emerald-500/20"
        />
        <Kpi
          label="Properties"
          value={String(overview.total_properties)}
          sub="active catalogue"
          icon={<Home className="size-5 text-muted-foreground" />}
          accent="bg-muted"
        />
      </div>

      <div className="flex flex-wrap gap-2 rounded-xl border border-border bg-card p-4">
        {LEAD_STATUSES.map((status) => (
          <span
            key={status}
            className="rounded-full border border-border px-3 py-1 text-xs text-muted-foreground"
          >
            {status}: <span className="font-mono text-foreground">{overview.by_status[status] ?? 0}</span>
          </span>
        ))}
      </div>
    </div>
  );
}
