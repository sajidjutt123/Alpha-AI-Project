"use client";

/**
 * Notification bell — unread badge, recent list, mark-all-read, and realtime
 * behaviour: every `notification.created` event fires a toast immediately,
 * bumps the badge, and (when the tab is hidden + permission granted) raises
 * a browser notification so hot leads surface even off-tab.
 */

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { Bell, BellRing, CheckCheck } from "lucide-react";

import { useRealtimeEvent } from "@/features/realtime/realtime-provider";
import { useToasts } from "@/features/notifications/toast-provider";
import { notificationsApi } from "@/lib/api";
import type { NotificationItem } from "@/types/api";
import { cn } from "@/lib/utils";

function timeAgo(iso: string): string {
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function NotificationBell() {
  const { push } = useToasts();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<NotificationItem[] | null>(null);
  const [unread, setUnread] = useState(0);
  const [permission, setPermission] = useState<NotificationPermission>("default");
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let active = true;
    async function bootstrap(): Promise<void> {
      try {
        const result = await notificationsApi.list();
        if (!active) return;
        setItems(result.items);
        setUnread(result.unread_count);
      } catch {
        if (active) setItems([]);
      }
      if (typeof Notification !== "undefined") {
        setPermission(Notification.permission);
      }
    }
    void bootstrap();
    return () => {
      active = false;
    };
  }, []);

  // Close the dropdown on outside clicks.
  useEffect(() => {
    if (!open) return;
    function onClick(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  const onNotificationCreated = useCallback(
    (payload: Record<string, unknown>) => {
      const title = String(payload.title ?? "Notification");
      const body = String(payload.body ?? "");
      const type = String(payload.type ?? "");
      const id = String(payload.id ?? crypto.randomUUID());
      const leadId = payload.lead_id ? String(payload.lead_id) : null;
      const createdAt = String(payload.created_at ?? new Date().toISOString());

      setUnread((count) => count + 1);
      setItems((current) =>
        current
          ? [
              {
                id,
                type: type as NotificationItem["type"],
                title,
                body,
                lead_id: leadId,
                read: false,
                created_at: createdAt,
              },
              ...current,
            ].slice(0, 30)
          : current,
      );
      push({ title, body, tone: type === "HOT_LEAD" ? "hot" : "info" });

      if (typeof Notification !== "undefined" && Notification.permission === "granted") {
        if (document.hidden) new Notification(title, { body, tag: id });
      }
    },
    [push],
  );
  useRealtimeEvent("notification.created", onNotificationCreated);

  async function markAllRead() {
    try {
      await notificationsApi.markAllRead();
      setUnread(0);
      setItems((current) => current?.map((item) => ({ ...item, read: true })) ?? null);
    } catch {
      // badge stays as-is; next open re-syncs with server truth
    }
  }

  async function enableBrowserNotifications() {
    if (typeof Notification === "undefined") return;
    const result = await Notification.requestPermission();
    setPermission(result);
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        onClick={() => setOpen((value) => !value)}
        aria-label={`Notifications (${unread} unread)`}
        className="relative flex size-9 items-center justify-center rounded-lg border border-border bg-card text-muted-foreground transition hover:text-foreground"
      >
        {unread > 0 ? (
          <BellRing className="size-4 text-primary" />
        ) : (
          <Bell className="size-4" />
        )}
        {unread > 0 && (
          <span className="absolute -right-1.5 -top-1.5 flex min-w-5 items-center justify-center rounded-full bg-destructive px-1.5 text-[10px] font-bold leading-5 text-destructive-foreground">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-11 z-40 w-80 rounded-xl border border-border bg-card p-2 shadow-xl shadow-black/30">
          <div className="flex items-center justify-between px-2 py-1.5">
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Notifications
            </p>
            <button
              onClick={markAllRead}
              className="flex items-center gap-1 text-xs text-muted-foreground transition hover:text-foreground"
            >
              <CheckCheck className="size-3.5" /> Mark all read
            </button>
          </div>
          <div className="max-h-80 overflow-y-auto">
            {items === null && (
              <p className="px-2 py-6 text-center text-xs text-muted-foreground">Loading…</p>
            )}
            {items?.length === 0 && (
              <p className="px-2 py-6 text-center text-xs text-muted-foreground">
                Nothing yet — new leads and hot-lead alerts land here live.
              </p>
            )}
            {items?.map((item) => {
              const content = (
                <div
                  className={cn(
                    "rounded-lg px-2.5 py-2",
                    item.read ? "opacity-60" : "bg-primary/5",
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-medium leading-tight">{item.title}</p>
                    {item.type === "HOT_LEAD" && !item.read && (
                      <span className="shrink-0 rounded bg-destructive/15 px-1.5 py-0.5 text-[10px] font-bold text-destructive">
                        HOT
                      </span>
                    )}
                  </div>
                  <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{item.body}</p>
                  <p className="mt-1 text-[10px] text-muted-foreground">
                    {timeAgo(item.created_at)}
                  </p>
                </div>
              );
              return item.lead_id ? (
                <Link
                  key={item.id}
                  href={`/dashboard/leads/${item.lead_id}`}
                  onClick={() => setOpen(false)}
                  className="block rounded-lg transition hover:bg-background"
                >
                  {content}
                </Link>
              ) : (
                <div key={item.id}>{content}</div>
              );
            })}
          </div>
          {typeof Notification !== "undefined" && permission === "default" && (
            <button
              onClick={enableBrowserNotifications}
              className="mt-1 w-full rounded-lg border border-border px-2 py-1.5 text-xs text-muted-foreground transition hover:text-foreground"
            >
              Enable browser notifications
            </button>
          )}
        </div>
      )}
    </div>
  );
}
