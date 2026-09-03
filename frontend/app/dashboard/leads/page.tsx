"use client";

import { useState } from "react";

import { KanbanBoard } from "@/features/leads/kanban";
import { LeadsTable } from "@/features/leads/leads-table";
import { cn } from "@/lib/utils";

export default function LeadsPage() {
  const [view, setView] = useState<"table" | "kanban">("kanban");

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Leads & Pipeline</h1>
          <p className="text-sm text-muted-foreground">
            Drag cards across the pipeline — illegal transitions are enforced by the API.
          </p>
        </div>
        <div className="flex rounded-lg border border-border p-1 text-xs">
          {(["kanban", "table"] as const).map((mode) => (
            <button
              key={mode}
              onClick={() => setView(mode)}
              className={cn(
                "rounded px-3 py-1.5 capitalize transition",
                view === mode ? "bg-primary/15 text-primary" : "text-muted-foreground",
              )}
            >
              {mode}
            </button>
          ))}
        </div>
      </div>

      {view === "kanban" ? <KanbanBoard /> : <LeadsTable />}
    </div>
  );
}
