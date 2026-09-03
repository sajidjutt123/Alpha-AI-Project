"use client";

/**
 * Session context — holds the auth token + agent profile.
 *
 * Local development authenticates via POST /auth/dev-login (seeded agent
 * email → JWT). Production swaps in Supabase Auth: the Supabase session's
 * access_token feeds the same `setTokenProvider` / Authorization header —
 * nothing else in the app changes (same downstream verification path).
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { agentsApi, authApi, setTokenProvider } from "@/lib/api";
import type { Me } from "@/types/api";

const STORAGE_KEY = "alpha.session.token";

interface SessionState {
  agent: Me | null;
  status: "loading" | "authenticated" | "anonymous";
  login: (email: string) => Promise<void>;
  logout: () => void;
}

const SessionContext = createContext<SessionState | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [agent, setAgent] = useState<Me | null>(null);
  const [status, setStatus] = useState<SessionState["status"]>("loading");

  useEffect(() => {
    let active = true;
    setTokenProvider(() =>
      typeof window === "undefined" ? null : window.localStorage.getItem(STORAGE_KEY),
    );

    async function bootstrap(): Promise<Me | null> {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (!stored) return null;
      try {
        return await agentsApi.me();
      } catch {
        window.localStorage.removeItem(STORAGE_KEY);
        return null;
      }
    }

    void bootstrap().then((me) => {
      if (!active) return;
      setAgent(me);
      setToken(me ? window.localStorage.getItem(STORAGE_KEY) : null);
      setStatus(me ? "authenticated" : "anonymous");
    });

    return () => {
      active = false;
    };
  }, []);

  const login = useCallback(async (email: string) => {
    const session = await authApi.devLogin(email);
    window.localStorage.setItem(STORAGE_KEY, session.token);
    setToken(session.token);
    setAgent(session.agent);
    setStatus("authenticated");
  }, []);

  const logout = useCallback(() => {
    window.localStorage.removeItem(STORAGE_KEY);
    setToken(null);
    setAgent(null);
    setStatus("anonymous");
  }, []);

  const value = useMemo<SessionState>(
    () => ({ agent, status, login, logout }),
    [agent, status, login, logout],
  );
  void token; // token lives in localStorage; provider wires it into api.ts
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionState {
  const context = useContext(SessionContext);
  if (!context) throw new Error("useSession must be used within SessionProvider");
  return context;
}
