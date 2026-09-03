# Alpha AI — Frontend

Next.js 16 (App Router) + TypeScript + Tailwind CSS 4. The agent command
center (login, Kanban, live conversations, analytics) lands Phase 7+.

## Structure

```
frontend/
  app/            App Router pages & layouts
  components/     shared UI components (shadcn/ui from Phase 7)
  features/       dashboard feature modules (see features/README.md)
  hooks/          shared client hooks
  lib/            API client, utilities, configuration
  types/          shared TypeScript contracts (mirror of backend schemas)
  proxy.ts        edge proxy — route gating (auth arrives Phase 7)
```

## Develop

```bash
cp .env.example .env.local
npm install
npm run dev        # http://localhost:3000
```

The status page polls the backend through the server-side proxy
(`/api/backend/*` → FastAPI `/api/v1/*`, see `next.config.ts`).

## Scripts

| Command | Description |
|---|---|
| `npm run dev` | Dev server (Turbopack) |
| `npm run build` | Production build |
| `npm run start` | Serve the production build |
| `npm run lint` | ESLint (next/core-web-vitals + typescript) |
