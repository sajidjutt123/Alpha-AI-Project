"use client";

import { useEffect, useState } from "react";

import { apiFetch } from "@/lib/api";
import type { HealthResponse } from "@/types/api";

export type BackendConnectionState = "checking" | "online" | "offline";

interface BackendHealth {
  state: BackendConnectionState;
  data: HealthResponse | null;
  checkedAt: Date | null;
}

const POLL_INTERVAL_MS = 30_000;

/** Poll the backend health endpoint and expose connection state. */
export function useBackendHealth(): BackendHealth {
  const [health, setHealth] = useState<BackendHealth>({
    state: "checking",
    data: null,
    checkedAt: null,
  });

  useEffect(() => {
    let active = true;

    async function poll() {
      try {
        const data = await apiFetch<HealthResponse>("/health");
        if (active) {
          setHealth({ state: "online", data, checkedAt: new Date() });
        }
      } catch {
        // `offline` is the represented error state, not a crash.
        if (active) {
          setHealth({ state: "offline", data: null, checkedAt: new Date() });
        }
      }
    }

    void poll();
    const timer = setInterval(() => void poll(), POLL_INTERVAL_MS);

    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);

  return health;
}
