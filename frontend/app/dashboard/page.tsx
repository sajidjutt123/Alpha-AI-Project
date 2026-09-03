"use client";

import { KpiCards } from "@/features/analytics/kpi-cards";

export default function DashboardOverviewPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Overview</h1>
        <p className="text-sm text-muted-foreground">
          Live pulse of your pipeline — AI-qualified leads, conversion, and catalogue.
        </p>
      </div>
      <KpiCards />
    </div>
  );
}
