"use client";

/** Dashboard shell: auth guard + sidebar navigation (responsive). */

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { Building2, KanbanSquare, LayoutDashboard, LogOut, Users } from "lucide-react";

import { useSession } from "@/features/auth/session";
import { NotificationBell } from "@/features/notifications/notification-bell";
import { ToastProvider } from "@/features/notifications/toast-provider";
import { RealtimeProvider, useRealtime } from "@/features/realtime/realtime-provider";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/dashboard/leads", label: "Leads & Pipeline", icon: Users },
  { href: "/dashboard/properties", label: "Properties", icon: Building2 },
];

/** Live-connection pill fed by the SSE stream state. */
function LiveBadge() {
  const { connection } = useRealtime();
  const map = {
    live: { label: "Live", dot: "bg-emerald-500", cls: "border-emerald-500/30 text-emerald-400" },
    connecting: { label: "Connecting", dot: "bg-amber-500 animate-pulse", cls: "border-amber-500/30 text-amber-400" },
    reconnecting: { label: "Reconnecting", dot: "bg-amber-500 animate-pulse", cls: "border-amber-500/30 text-amber-400" },
    offline: { label: "Offline", dot: "bg-muted-foreground", cls: "border-border text-muted-foreground" },
  } as const;
  const state = map[connection];
  return (
    <span
      className={cn(
        "flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium",
        state.cls,
      )}
    >
      <span className={cn("size-1.5 rounded-full", state.dot)} />
      {state.label}
    </span>
  );
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { status, agent, logout } = useSession();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (status === "anonymous") router.replace("/login");
  }, [status, router]);

  if (status !== "authenticated") {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="size-8 animate-pulse rounded-full bg-primary/40" />
      </div>
    );
  }

  return (
    <ToastProvider>
      <RealtimeProvider>
        <div className="flex min-h-screen">
      <aside className="hidden w-60 shrink-0 flex-col border-r border-border bg-card/40 p-4 md:flex">
        <Link href="/" className="mb-8 flex items-center gap-2.5 px-2">
          <div className="flex size-9 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-accent text-base font-black text-background">
            α
          </div>
          <div>
            <p className="text-sm font-semibold">Alpha AI</p>
            <p className="text-[10px] text-muted-foreground">Command Center</p>
          </div>
        </Link>
        <nav className="space-y-1">
          {NAV.map((item) => {
            const active =
              item.href === "/dashboard"
                ? pathname === "/dashboard"
                : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition",
                  active
                    ? "border border-primary/30 bg-primary/10 text-primary"
                    : "border border-transparent text-muted-foreground hover:bg-card hover:text-foreground",
                )}
              >
                <item.icon className="size-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="mt-auto space-y-3 border-t border-border pt-4">
          <div className="px-2">
            <p className="truncate text-sm font-medium">{agent?.name}</p>
            <p className="truncate text-xs text-muted-foreground">
              {agent?.role} · {agent?.email}
            </p>
          </div>
          <button
            onClick={() => {
              logout();
              router.push("/login");
            }}
            className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-muted-foreground transition hover:bg-destructive/10 hover:text-destructive"
          >
            <LogOut className="size-4" /> Sign out
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-border px-4 py-3 md:hidden">
          <KanbanSquare className="size-5 text-primary" />
          <span className="text-sm font-semibold">Alpha AI</span>
          <div className="ml-auto flex items-center gap-2">
            <LiveBadge />
            <NotificationBell />
          </div>
          <button
            onClick={() => {
              logout();
              router.push("/login");
            }}
            className="text-xs text-muted-foreground"
          >
            sign out
          </button>
        </header>
        <div className="hidden items-center justify-end gap-3 border-b border-border px-8 py-2.5 md:flex">
          <LiveBadge />
          <NotificationBell />
        </div>
        <main className="min-w-0 flex-1 p-4 md:p-8">{children}</main>
      </div>
    </div>
      </RealtimeProvider>
    </ToastProvider>
  );
}
