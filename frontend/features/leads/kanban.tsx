"use client";

/**
 * Kanban board — drag a card between status columns (native HTML5 DnD).
 * Drops run through PATCH /leads/{id} which enforces the transition map;
 * illegal moves are rejected by the backend and the card snaps back.
 */

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { useRealtimeEvent } from "@/features/realtime/realtime-provider";
import { leadsApi } from "@/lib/api";
import type { Lead, LeadStatus } from "@/types/api";
import { LEAD_STATUSES, ScoreBar, temperature } from "@/components/dash/ui";
import { cn } from "@/lib/utils";

export function KanbanBoard() {
  const [leads, setLeads] = useState<Lead[] | null>(null);
  const [dragging, setDragging] = useState<Lead | null>(null);
  const [dropTarget, setDropTarget] = useState<LeadStatus | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const refresh = useCallback(() => setTick((current) => current + 1), []);

  // Realtime board updates (Phase 8): new leads and AI-driven status/score
  // changes arrive over SSE; coalesce bursts (multi-event webhook runs) into
  // one refetch after a short debounce.
  const debounce = useRef<ReturnType<typeof setTimeout> | null>(null);
  const refreshSoon = useCallback(() => {
    if (debounce.current) clearTimeout(debounce.current);
    debounce.current = setTimeout(() => refresh(), 400);
  }, [refresh]);
  useEffect(() => () => {
    if (debounce.current) clearTimeout(debounce.current);
  }, []);
  useRealtimeEvent("lead.created", refreshSoon);
  useRealtimeEvent("lead.updated", refreshSoon);

  useEffect(() => {
    let active = true;
    async function fetchBoard() {
      try {
        const result = await leadsApi.list({ limit: 100 });
        if (active) setLeads(result.items);
      } catch {
        if (active) setNotice("Failed to load leads");
      }
    }
    void fetchBoard();
    return () => {
      active = false;
    };
  }, [tick]);

  async function moveTo(lead: Lead, target: LeadStatus) {
    if (lead.status === target) return;
    setLeads((current) =>
      current?.map((item) => (item.id === lead.id ? { ...item, status: target } : item)) ?? null,
    );
    try {
      await leadsApi.update(lead.id, { status: target });
      setNotice(null);
    } catch (cause) {
      setNotice(cause instanceof Error ? cause.message : "Move rejected");
      refresh(); // snap back to server truth
    }
  }

  if (!leads) {
    return (
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3 xl:grid-cols-5">
        {LEAD_STATUSES.map((status) => (
          <div key={status} className="h-64 animate-pulse rounded-xl bg-card" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {notice && (
        <p className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
          {notice}
        </p>
      )}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3 xl:grid-cols-5">
        {LEAD_STATUSES.map((status) => {
          const columnLeads = leads.filter((lead) => lead.status === status);
          return (
            <div
              key={status}
              onDragOver={(event) => {
                event.preventDefault();
                setDropTarget(status);
              }}
              onDragLeave={() => setDropTarget((t) => (t === status ? null : t))}
              onDrop={(event) => {
                event.preventDefault();
                setDropTarget(null);
                if (dragging) void moveTo(dragging, status);
                setDragging(null);
              }}
              className={cn(
                "min-h-64 rounded-xl border p-3 transition",
                dropTarget === status
                  ? "border-primary bg-primary/5"
                  : "border-border bg-card/40",
              )}
            >
              <div className="mb-3 flex items-center justify-between">
                <span className="text-xs font-semibold tracking-wide">{status}</span>
                <span className="rounded-full bg-muted px-2 py-0.5 font-mono text-[10px] text-muted-foreground">
                  {columnLeads.length}
                </span>
              </div>
              <div className="space-y-2">
                {columnLeads.map((lead) => {
                  const t = temperature(lead.qualification_score);
                  return (
                    <div
                      key={lead.id}
                      draggable
                      onDragStart={() => setDragging(lead)}
                      onDragEnd={() => setDragging(null)}
                      className={cn(
                        "cursor-grab rounded-lg border border-border bg-card p-3 transition active:cursor-grabbing",
                        dragging?.id === lead.id && "opacity-50",
                      )}
                    >
                      <Link
                        href={`/dashboard/leads/${lead.id}`}
                        className="block text-sm font-medium hover:text-primary"
                      >
                        {lead.name ?? lead.phone}
                      </Link>
                      <p className="mt-0.5 truncate text-[11px] text-muted-foreground">
                        {lead.preferred_location ?? lead.phone}
                      </p>
                      <div className="mt-2 flex items-center justify-between gap-2">
                        <ScoreBar score={lead.qualification_score} />
                        <span
                          className={cn("size-2 rounded-full", t.className)}
                          title={t.label}
                        />
                      </div>
                      <select
                        value={lead.status}
                        onChange={(event) =>
                          void moveTo(lead, event.target.value as LeadStatus)
                        }
                        className="mt-2 w-full rounded border border-border bg-background px-1.5 py-1 text-[10px] text-muted-foreground outline-none"
                      >
                        {LEAD_STATUSES.map((s) => (
                          <option key={s} value={s}>
                            move to {s}
                          </option>
                        ))}
                      </select>
                    </div>
                  );
                })}
                {columnLeads.length === 0 && (
                  <p className="rounded-lg border border-dashed border-border/60 p-3 text-center text-[11px] text-muted-foreground">
                    drop here
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
