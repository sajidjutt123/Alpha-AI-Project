"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Search } from "lucide-react";

import { leadsApi } from "@/lib/api";
import type { Lead } from "@/types/api";
import { LEAD_STATUSES, ScoreBar, StatusBadge, formatBudget, timeAgo } from "@/components/dash/ui";

export function LeadsTable() {
  const [leads, setLeads] = useState<Lead[] | null>(null);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState<string>("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const [error, setError] = useState(false);
  const limit = 20;

  const load = useCallback(async () => {
    try {
      const result = await leadsApi.list({
        status: status || undefined,
        q: query || undefined,
        limit,
        offset: page * limit,
      });
      setLeads(result.items);
      setTotal(result.total);
      setError(false);
    } catch {
      setError(true);
    }
  }, [status, query, page]);

  useEffect(() => {
    const timer = setTimeout(() => void load(), query ? 300 : 0);
    return () => clearTimeout(timer);
  }, [load, query]);

  const pages = Math.max(1, Math.ceil(total / limit));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-56">
          <Search className="absolute top-2.5 left-3 size-4 text-muted-foreground" />
          <input
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setPage(0);
            }}
            placeholder="Search name, phone, or location…"
            className="w-full rounded-lg border border-border bg-card py-2 pr-3 pl-9 text-sm outline-none focus:border-primary"
          />
        </div>
        <select
          value={status}
          onChange={(event) => {
            setStatus(event.target.value);
            setPage(0);
          }}
          className="rounded-lg border border-border bg-card px-3 py-2 text-sm outline-none focus:border-primary"
        >
          <option value="">All statuses</option>
          {LEAD_STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      {error && (
        <p className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          Failed to load leads.
        </p>
      )}
      {!error && leads === null && (
        <div className="space-y-2">
          {[0, 1, 2, 3, 4].map((i) => (
            <div key={i} className="h-12 animate-pulse rounded-lg bg-card" />
          ))}
        </div>
      )}

      {leads && (
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full min-w-[860px] text-sm">
            <thead>
              <tr className="border-b border-border bg-card text-left text-xs tracking-wide text-muted-foreground uppercase">
                <th className="px-4 py-3">Lead</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Requirements</th>
                <th className="px-4 py-3">Budget</th>
                <th className="px-4 py-3">Score</th>
                <th className="px-4 py-3">Last activity</th>
              </tr>
            </thead>
            <tbody>
              {leads.map((lead) => (
                <tr
                  key={lead.id}
                  className="border-b border-border/60 transition hover:bg-card/60"
                >
                  <td className="px-4 py-3">
                    <Link href={`/dashboard/leads/${lead.id}`} className="group">
                      <span className="font-medium group-hover:text-primary">
                        {lead.name ?? "Unnamed"}
                      </span>
                      <span className="block text-xs text-muted-foreground">{lead.phone}</span>
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={lead.status} />
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">
                    {[
                      lead.property_type,
                      lead.bedrooms ? `${lead.bedrooms} bed` : null,
                      lead.preferred_location,
                    ]
                      .filter(Boolean)
                      .join(" · ") || "—"}
                  </td>
                  <td className="px-4 py-3 text-xs">
                    {formatBudget(lead.budget_min, lead.budget_max)}
                  </td>
                  <td className="px-4 py-3">
                    <ScoreBar score={lead.qualification_score} />
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">
                    {timeAgo(lead.updated_at)}
                  </td>
                </tr>
              ))}
              {leads.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-10 text-center text-sm text-muted-foreground">
                    No leads match these filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {leads && pages > 1 && (
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>
            Page {page + 1} of {pages} · {total} leads
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="rounded-lg border border-border px-3 py-1 disabled:opacity-40"
            >
              Previous
            </button>
            <button
              onClick={() => setPage((p) => Math.min(pages - 1, p + 1))}
              disabled={page >= pages - 1}
              className="rounded-lg border border-border px-3 py-1 disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
