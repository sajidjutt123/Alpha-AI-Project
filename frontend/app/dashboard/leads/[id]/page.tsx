"use client";

/** Lead profile: facts + score, AI qualification, transcript, matches. */

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowLeft, Bot, Phone } from "lucide-react";

import { MatchCard } from "@/features/properties/match-cards";
import { Transcript } from "@/features/conversations/transcript";
import { leadsApi } from "@/lib/api";
import type { LeadDetail } from "@/types/api";
import { ScoreBar, StatusBadge, formatBudget } from "@/components/dash/ui";

function Fact({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-border/50 py-2 last:border-0">
      <span className="text-xs tracking-wide text-muted-foreground uppercase">{label}</span>
      <span className="text-right text-sm">{value ?? "—"}</span>
    </div>
  );
}

export default function LeadProfilePage() {
  const params = useParams<{ id: string }>();
  const [lead, setLead] = useState<LeadDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    leadsApi
      .get(params.id)
      .then(setLead)
      .catch((cause: unknown) =>
        setError(cause instanceof Error ? cause.message : "Failed to load lead"),
      );
  }, [params.id]);

  if (error) {
    return (
      <div className="space-y-4">
        <Link href="/dashboard/leads" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-4" /> back to leads
        </Link>
        <p className="rounded-xl border border-destructive/40 bg-destructive/10 p-6 text-sm text-destructive">
          {error}
        </p>
      </div>
    );
  }
  if (!lead) {
    return <div className="h-96 animate-pulse rounded-xl bg-card" />;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <Link
          href="/dashboard/leads"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" /> leads
        </Link>
        <span className="text-muted-foreground">/</span>
        <h1 className="text-2xl font-semibold tracking-tight">{lead.name ?? "Unnamed lead"}</h1>
        <StatusBadge status={lead.status} />
        <span className="ml-auto">
          <ScoreBar score={lead.qualification_score} />
        </span>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[320px_1fr]">
        <div className="space-y-6">
          <section className="rounded-xl border border-border bg-card p-4">
            <p className="mb-2 flex items-center gap-2 text-xs font-semibold tracking-wide uppercase">
              <Phone className="size-3.5" /> Contact & requirements
            </p>
            <Fact label="Phone" value={lead.phone} />
            <Fact label="Email" value={lead.email} />
            <Fact label="Intent" value={lead.intent} />
            <Fact label="Location" value={lead.preferred_location} />
            <Fact label="Type" value={lead.property_type} />
            <Fact label="Bedrooms" value={lead.bedrooms} />
            <Fact label="Budget" value={formatBudget(lead.budget_min, lead.budget_max)} />
            <Fact label="Urgency" value={lead.urgency_score ? `${lead.urgency_score}/10` : null} />
            <Fact label="Created" value={new Date(lead.created_at).toLocaleString()} />
          </section>

          <section className="rounded-xl border border-border bg-card p-4">
            <p className="mb-2 flex items-center gap-2 text-xs font-semibold tracking-wide uppercase">
              <Bot className="size-3.5 text-primary" /> AI qualification
            </p>
            {lead.summary ? (
              <p className="text-sm leading-relaxed text-muted-foreground">{lead.summary}</p>
            ) : (
              <p className="text-sm text-muted-foreground italic">
                The AI assistant will summarize this lead as the conversation develops.
              </p>
            )}
          </section>

          <section className="space-y-3">
            <p className="text-xs font-semibold tracking-wide uppercase">
              Matched properties ({lead.matched_properties.length})
            </p>
            {lead.matched_properties.length > 0 ? (
              lead.matched_properties.map((match) => (
                <MatchCard key={match.property_id} match={match} />
              ))
            ) : (
              <p className="rounded-xl border border-dashed border-border p-4 text-xs text-muted-foreground">
                No matches yet — matches appear automatically once requirements are
                specific enough.
              </p>
            )}
          </section>
        </div>

        <Transcript leadId={lead.id} initialMessages={lead.messages} />
      </div>
    </div>
  );
}
