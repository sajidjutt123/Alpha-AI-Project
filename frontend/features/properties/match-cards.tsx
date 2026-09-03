"use client";

/** Matched property cards with score + reason (lead detail view). */

import { Home } from "lucide-react";

import type { MatchedProperty } from "@/types/api";
import { formatPkr } from "@/components/dash/ui";

export function MatchCard({ match }: { match: MatchedProperty }) {
  return (
    <div className="rounded-xl border border-primary/30 bg-primary/5 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold">{match.title}</p>
          <p className="mt-0.5 flex items-center gap-1 text-xs text-muted-foreground">
            <Home className="size-3" /> {match.location}
          </p>
        </div>
        <span className="rounded-full bg-primary/15 px-2 py-1 font-mono text-xs font-bold text-primary">
          {match.match_score}%
        </span>
      </div>
      <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
        <span className="rounded-full border border-border px-2 py-0.5">
          {formatPkr(match.price)}
        </span>
        <span className="rounded-full border border-border px-2 py-0.5">
          {match.property_type}
        </span>
        {match.bedrooms != null && (
          <span className="rounded-full border border-border px-2 py-0.5">
            {match.bedrooms} bed
          </span>
        )}
      </div>
      {match.reason && (
        <p className="mt-3 border-t border-border/60 pt-2 text-xs leading-relaxed text-muted-foreground italic">
          {match.reason}
        </p>
      )}
    </div>
  );
}
