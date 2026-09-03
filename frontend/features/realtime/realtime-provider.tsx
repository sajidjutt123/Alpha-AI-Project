"use client";

/**
 * Realtime context — one SSE connection per authenticated session.
 *
 * The provider owns the fetch-based stream (lib/realtime.ts) and fans events
 * out to subscribers. Components opt in with `useRealtimeEvent(type, handler)`
 * — e.g. the kanban board refreshes on `lead.updated`, the transcript appends
 * on `message.created`. Multi-instance deployments swap the in-process event
 * bus for Redis pub/sub server-side; this client is unchanged (see
 * docs/architecture.md).
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { useSession } from "@/features/auth/session";
import {
  consumeRealtimeStream,
  reconnectDelayMs,
  type RealtimeEvent,
} from "@/lib/realtime";

export type ConnectionState = "connecting" | "live" | "reconnecting" | "offline";

type Handler = (payload: Record<string, unknown>) => void;

interface RealtimeState {
  connection: ConnectionState;
  lastEventAt: number | null;
}

const RealtimeContext = createContext<RealtimeState | null>(null);

/** Ref-based subscription registry (stable identity across renders). */
const RealtimeSubscriptionContext = createContext<
  ((type: string, handler: Handler) => () => void) | null
>(null);

export function RealtimeProvider({ children }: { children: ReactNode }) {
  const { status } = useSession();
  const [connection, setConnection] = useState<ConnectionState>("offline");
  const [lastEventAt, setLastEventAt] = useState<number | null>(null);

  /** type → handlers. "*" receives every event (notification bell). */
  const handlersRef = useRef<Map<string, Set<Handler>>>(new Map());

  const subscribe = useCallback((type: string, handler: Handler) => {
    const map = handlersRef.current;
    const set = map.get(type) ?? new Set<Handler>();
    set.add(handler);
    map.set(type, set);
    return () => {
      set.delete(handler);
      if (set.size === 0) map.delete(type);
    };
  }, []);

  const dispatch = useCallback((event: RealtimeEvent) => {
    setLastEventAt(Date.now());
    handlersRef.current.get(event.type)?.forEach((handler) => handler(event.payload));
    handlersRef.current.get("*")?.forEach((handler) => handler(event.payload));
  }, []);

  useEffect(() => {
    if (status !== "authenticated") return;

    const controller = new AbortController();
    let attempt = 0;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    async function connect(): Promise<void> {
      setConnection(attempt === 0 ? "connecting" : "reconnecting");
      await consumeRealtimeStream(controller.signal, {
        onEvent: dispatch,
        onOpen: () => {
          attempt = 0;
          setConnection("live");
        },
        onClose: (reason) => {
          if (stopped || controller.signal.aborted) return;
          if (reason === "done") {
            // Server closed cleanly (deploy/restart) — reconnect immediately.
            attempt = 0;
          }
          timer = setTimeout(() => void connect(), reconnectDelayMs(attempt++));
        },
      });
    }

    void connect();
    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
      controller.abort();
      setConnection("offline");
    };
  }, [status, dispatch]);

  // Derived view state: without a session there is no stream, so report
  // "offline" regardless of any stale connection value (no setState-in-effect).
  const effectiveConnection =
    status === "authenticated" ? connection : ("offline" as ConnectionState);
  const value = useMemo<RealtimeState>(
    () => ({ connection: effectiveConnection, lastEventAt }),
    [effectiveConnection, lastEventAt],
  );

  return (
    <RealtimeContext.Provider value={value}>
      <RealtimeSubscriptionContext.Provider value={subscribe}>
        {children}
      </RealtimeSubscriptionContext.Provider>
    </RealtimeContext.Provider>
  );
}

export function useRealtimeEvent(type: string, handler: Handler): void {
  const subscribe = useContext(RealtimeSubscriptionContext);
  const latest = useRef<Handler>(handler);
  useEffect(() => {
    latest.current = handler; // keep the closure fresh without resubscribing
  });

  useEffect(() => {
    if (!subscribe) return;
    return subscribe(type, (payload) => latest.current(payload));
  }, [subscribe, type]);
}

export function useRealtime(): RealtimeState {
  const context = useContext(RealtimeContext);
  if (!context) throw new Error("useRealtime must be used within RealtimeProvider");
  return context;
}
