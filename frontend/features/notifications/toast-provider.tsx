"use client";

/**
 * Minimal toast stack (no external dependency) — used by the realtime layer
 * to surface `notification.created` events (new lead / hot lead / handoff)
 * the moment they happen, without a page refresh.
 */

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { BellRing, CheckCircle2, X } from "lucide-react";

import { cn } from "@/lib/utils";

export interface Toast {
  id: number;
  title: string;
  body?: string;
  tone: "info" | "hot";
}

interface ToastState {
  push: (toast: Omit<Toast, "id">) => void;
}

const ToastContext = createContext<ToastState | null>(null);
const TOAST_MS = 6_000;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const push = useCallback(
    (toast: Omit<Toast, "id">) => {
      const id = nextId.current++;
      setToasts((current) => [...current.slice(-3), { ...toast, id }]);
      setTimeout(() => dismiss(id), TOAST_MS);
    },
    [dismiss],
  );

  const value = useMemo<ToastState>(() => ({ push }), [push]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed right-4 top-4 z-50 flex w-80 flex-col gap-2">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            role="status"
            className={cn(
              "pointer-events-auto flex items-start gap-2.5 rounded-xl border bg-card p-3 shadow-lg shadow-black/20",
              toast.tone === "hot"
                ? "border-destructive/40"
                : "border-border",
            )}
          >
            {toast.tone === "hot" ? (
              <BellRing className="mt-0.5 size-4 shrink-0 text-destructive" />
            ) : (
              <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-primary" />
            )}
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium leading-tight">{toast.title}</p>
              {toast.body && (
                <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">
                  {toast.body}
                </p>
              )}
            </div>
            <button
              onClick={() => dismiss(toast.id)}
              aria-label="Dismiss notification"
              className="text-muted-foreground transition hover:text-foreground"
            >
              <X className="size-3.5" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToasts(): ToastState {
  const context = useContext(ToastContext);
  if (!context) throw new Error("useToasts must be used within ToastProvider");
  return context;
}
