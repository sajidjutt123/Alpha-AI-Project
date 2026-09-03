import { BackendStatus } from "@/components/status/backend-status";

const PHASES = [
  { id: 1, name: "Architecture & Scaffolding", status: "done" },
  { id: 2, name: "Database & Auth", status: "done" },
  { id: 3, name: "FastAPI Core APIs", status: "done" },
  { id: 4, name: "Twilio Webhook Pipeline", status: "done" },
  { id: 5, name: "AI Engine", status: "done" },
  { id: 6, name: "Property Matching", status: "done" },
  { id: 7, name: "Agent Dashboard", status: "next" },
  { id: 8, name: "Realtime & Notifications", status: "todo" },
  { id: 9, name: "Testing & Security Audit", status: "todo" },
  { id: 10, name: "Deployment", status: "todo" },
  { id: 11, name: "Demo & Sales Package", status: "todo" },
] as const;

const STACK = [
  "Next.js 16",
  "TypeScript",
  "Tailwind CSS 4",
  "FastAPI",
  "PostgreSQL / Supabase",
  "OpenAI + LangGraph",
  "Twilio WhatsApp/SMS",
];

const STATUS_STYLES = {
  done: "border-primary/40 bg-primary/10 text-primary",
  next: "border-accent/40 bg-accent/10 text-accent",
  todo: "border-border bg-muted text-muted-foreground",
} as const;

const STATUS_LABELS = { done: "✓ complete", next: "up next", todo: "planned" } as const;

export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-5xl flex-col gap-12 px-6 py-16">
      <header className="flex flex-col gap-5">
        <div className="flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-accent text-lg font-black text-background">
            α
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Alpha AI</h1>
            <p className="text-xs text-muted-foreground">
              Real-Estate Lead Qualification & Sales Automation
            </p>
          </div>
        </div>
        <p className="max-w-2xl text-3xl leading-tight font-semibold tracking-tight text-balance md:text-4xl">
          A 24/7 AI sales assistant that turns WhatsApp &amp; SMS conversations
          into qualified, property-matched leads.
        </p>
        <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">
          Foundations are live: the monorepo, FastAPI service, and this
          dashboard shell. Conversational AI, lead qualification, and the
          command center arrive phase by phase.
        </p>
      </header>

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-medium tracking-wide text-muted-foreground uppercase">
          System Status
        </h2>
        <BackendStatus />
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-medium tracking-wide text-muted-foreground uppercase">
          Build Roadmap
        </h2>
        <ol className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {PHASES.map((phase) => (
            <li
              key={phase.id}
              className={`flex items-center justify-between gap-3 rounded-lg border px-4 py-3 text-sm ${STATUS_STYLES[phase.status]}`}
            >
              <span className="flex items-center gap-3">
                <span className="font-mono text-xs opacity-70">
                  {String(phase.id).padStart(2, "0")}
                </span>
                <span className={phase.status === "todo" ? "" : "font-medium"}>
                  {phase.name}
                </span>
              </span>
              <span className="text-[10px] whitespace-nowrap uppercase">
                {STATUS_LABELS[phase.status]}
              </span>
            </li>
          ))}
        </ol>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-medium tracking-wide text-muted-foreground uppercase">
          Stack
        </h2>
        <ul className="flex flex-wrap gap-2">
          {STACK.map((item) => (
            <li
              key={item}
              className="rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground"
            >
              {item}
            </li>
          ))}
        </ul>
      </section>

      <footer className="mt-auto border-t border-border pt-6 text-xs text-muted-foreground">
        Alpha AI · Phases 1–6 complete ·{" "}
        <a href="/login" className="text-primary underline underline-offset-2">
          Agent sign-in
        </a>{" "}
        unlocks the command center ·{" "}
        <code className="rounded bg-muted px-1 py-0.5">/dashboard</code>
      </footer>
    </main>
  );
}
