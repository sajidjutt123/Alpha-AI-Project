# Deployment

Target topology (Phase 10 — configured then, prepared now):

| Component | Platform |
|---|---|
| Frontend | Vercel (Next.js) |
| Backend | Railway or Render (Docker) |
| Database | Supabase (PostgreSQL + Auth + Realtime) |
| Messaging | Twilio (production WhatsApp sender + webhook URL) |
| Monitoring | Sentry + platform logs |

## Local development (today)

```bash
cp .env.example .env

# database + backend
docker compose up -d

# frontend (separate terminal)
cd frontend && npm install && npm run dev   # http://localhost:3000
```

Backend API: `http://localhost:8000/api/v1/docs`

## Environment

- Every deploy reads from platform env vars — images are built once and
  promoted (no secrets baked into builds).
- `ENVIRONMENT` switches behavior (docs exposure, CORS, logging verbosity).
- Production checklist (domain, HTTPS, webhook URL, rate limits, Sentry)
  is completed in Phase 10.

Detailed step-by-step runbooks (Vercel/Railway/Supabase console walkthroughs)
are added in Phase 10.
