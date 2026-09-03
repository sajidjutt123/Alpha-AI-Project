"use client";

/** Conversation transcript + agent takeover composer (live chat). */

import { useCallback, useState } from "react";
import { Bot, MessageSquare, Send, User } from "lucide-react";

import { useRealtimeEvent } from "@/features/realtime/realtime-provider";
import { leadsApi } from "@/lib/api";
import type { AgentMessage, TranscriptMessage } from "@/types/api";
import { cn } from "@/lib/utils";

function SenderAvatar({ sender }: { sender: TranscriptMessage["sender_type"] }) {
  if (sender === "CUSTOMER") return <User className="size-3.5 text-muted-foreground" />;
  if (sender === "AI") return <Bot className="size-3.5 text-primary" />;
  return <MessageSquare className="size-3.5 text-accent" />;
}

export function Transcript({
  leadId,
  initialMessages,
}: {
  leadId: string;
  initialMessages: TranscriptMessage[];
}) {
  const [messages, setMessages] = useState(initialMessages);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Live streaming (Phase 8): inbound WhatsApp/SMS replies and AI responses
  // for THIS lead append to the transcript in real time via SSE.
  const onMessageCreated = useCallback(
    (payload: Record<string, unknown>) => {
      if (String(payload.lead_id ?? "") !== leadId) return;
      setMessages((current) => {
        if (current.some((message) => message.id === String(payload.message_id))) {
          return current; // own agent sends are already appended locally
        }
        return [
          ...current,
          {
            id: String(payload.message_id),
            sender_type: (payload.sender_type as TranscriptMessage["sender_type"]) ?? "SYSTEM",
            content: String(payload.preview ?? ""),
            channel: "WHATSAPP",
            created_at: new Date().toISOString(),
          },
        ];
      });
    },
    [leadId],
  );
  useRealtimeEvent("message.created", onMessageCreated);

  async function send(event: React.FormEvent) {
    event.preventDefault();
    const content = draft.trim();
    if (!content || busy) return;
    setBusy(true);
    setError(null);
    try {
      const sent: AgentMessage = await leadsApi.sendMessage(leadId, content);
      setMessages((current) => [
        ...current,
        {
          id: sent.id,
          sender_type: sent.sender_type,
          content: sent.content,
          channel: sent.channel,
          created_at: sent.created_at,
        },
      ]);
      setDraft("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Send failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-96 flex-col rounded-xl border border-border bg-card">
      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {messages.length === 0 && (
          <p className="py-10 text-center text-sm text-muted-foreground">
            No messages yet — the AI greets new leads automatically.
          </p>
        )}
        {messages.map((message) => (
          <div
            key={message.id}
            className={cn(
              "max-w-[85%] rounded-xl px-3 py-2 text-sm",
              message.sender_type === "CUSTOMER" && "ml-0 border border-border bg-background",
              message.sender_type === "AI" && "ml-auto border border-primary/30 bg-primary/10",
              message.sender_type === "AGENT" && "ml-auto border border-accent/30 bg-accent/10",
              message.sender_type === "SYSTEM" &&
                "mx-auto border border-dashed border-border/60 bg-transparent text-center text-xs text-muted-foreground",
            )}
          >
            {message.sender_type !== "SYSTEM" && (
              <p className="mb-1 flex items-center gap-1.5 text-[10px] tracking-wide text-muted-foreground uppercase">
                <SenderAvatar sender={message.sender_type} />
                {message.sender_type === "CUSTOMER"
                  ? `Customer · ${message.channel}`
                  : message.sender_type === "AI"
                    ? "Alpha AI"
                    : "You"}
              </p>
            )}
            {message.content}
          </div>
        ))}
      </div>

      {error && (
        <p className="mx-4 mb-2 rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-1.5 text-xs text-destructive">
          {error}
        </p>
      )}

      <form onSubmit={send} className="flex gap-2 border-t border-border p-3">
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Take over the conversation…"
          className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
        />
        <button
          type="submit"
          disabled={busy || !draft.trim()}
          className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground transition hover:opacity-90 disabled:opacity-40"
        >
          <Send className="size-4" />
        </button>
      </form>
    </div>
  );
}
