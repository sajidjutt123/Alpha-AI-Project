"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { useSession } from "@/features/auth/session";

const DEMO_EMAILS = [
  { email: "ahmed@alphaestates.pk", label: "Ahmed Raza · Owner, Alpha Estates (Lahore)" },
  { email: "hassan@galaxyproperties.pk", label: "Hassan Sheikh · Owner, Galaxy Properties (Karachi)" },
];

export function LoginForm() {
  const { login } = useSession();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email.trim());
      router.push("/dashboard");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  async function loginAs(demoEmail: string) {
    setEmail(demoEmail);
    setBusy(true);
    setError(null);
    try {
      await login(demoEmail);
      router.push("/dashboard");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="w-full max-w-md space-y-6">
      <div className="space-y-2 text-center">
        <div className="mx-auto flex size-12 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-accent text-xl font-black text-background">
          α
        </div>
        <h1 className="text-2xl font-semibold tracking-tight">Alpha AI Command Center</h1>
        <p className="text-sm text-muted-foreground">
          Sign in with your agent email to operate leads, conversations, and matches.
        </p>
      </div>

      <form onSubmit={submit} className="space-y-4 rounded-xl border border-border bg-card p-6">
        <label className="block space-y-2">
          <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Agent email
          </span>
          <input
            type="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@agency.pk"
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
          />
        </label>
        {error && (
          <p className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition hover:opacity-90 disabled:opacity-50"
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
        <p className="text-center text-[11px] text-muted-foreground">
          Development mode — Supabase Auth takes over in production.
        </p>
      </form>

      <div className="space-y-2 rounded-xl border border-border bg-card p-4">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Demo accounts (seeded)
        </p>
        {DEMO_EMAILS.map((demo) => (
          <button
            key={demo.email}
            onClick={() => void loginAs(demo.email)}
            disabled={busy}
            className="w-full rounded-lg border border-border px-3 py-2 text-left text-xs transition hover:border-primary disabled:opacity-50"
          >
            <span className="font-medium">{demo.label}</span>
            <span className="block text-muted-foreground">{demo.email}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
