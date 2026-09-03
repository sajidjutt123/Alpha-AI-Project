# Deployment Runbook (Phase 10)

Target topology:

| Component | Platform | Artifact |
|---|---|---|
| Frontend | **Vercel** (or the `frontend/Dockerfile` anywhere containers run) | standalone Next.js build |
| Backend | **Railway** or **Render** (Docker) | `backend/Dockerfile` (repo-root context) |
| Database | **Supabase** (or any Postgres 16) | SQL migrations `database/migrations/` |
| Messaging | Twilio (production WhatsApp sender + webhook URL) | env config |
| Monitoring | Sentry (optional) + platform logs | `SENTRY_DSN` |

Everything below is configured in-repo and rehearsed locally:

- `backend/Dockerfile` — multi-stage, non-root, healthcheck, migrations inside
  the image, `--proxy-headers` for platform proxies.
- `frontend/Dockerfile` — standalone `node server.js` runtime.
- `docker-compose.prod.yml` — the whole stack on one host (also the local
  dress rehearsal: db → migrate → backend → frontend with health gating).
- `render.yaml` / `railway.json` / `vercel.json` — config-as-code.
- `python -m app.db.bootstrap_org` — first-organization provisioning CLI.

> **Verified here:** Dockerfiles/config syntax, the standalone production
> build serving the live stack (proxy, auth, CSP headers), migrations via
> `MIGRATIONS_DIR`, and the bootstrap CLI. The cloud-console steps below are
> the standard flows for each platform — they need your accounts/keys, which
> never enter this repo.

---

## 1. Database — Supabase (or any Postgres 16)

1. Create a project; note the **region** (pick the one nearest your
   customers — PK market: `ap-southeast-1` Singapore).
2. Get the **direct connection** string (Project Settings → Database).
   Use the **session/direct** port for migrations (transaction-mode
   poolers break session-level DDL).
3. Run migrations from your machine (repo root):

   ```bash
   cd backend
   pip install -r requirements.txt
   export ADMIN_DATABASE_URL="postgresql://postgres:<pw>@<host>:5432/postgres"
   export APP_DB_PASSWORD="<generate a strong password>"   # becomes alpha_app's password
   python -m app.db.migrate
   ```

   This creates the schema, the least-privilege `alpha_app` role (RLS-bound),
   and the SECURITY DEFINER lookup functions. Idempotent — safe to re-run on
   later deploys. (`schema.sql` exists for a one-shot alternative, but prefer
   the runner: it tracks applied versions.)

4. The app's runtime connection (`DATABASE_URL`) uses the **pooler** URI as
   the `alpha_app` role: `postgresql+asyncpg://alpha_app:<APP_DB_PASSWORD>@.../postgres`.
5. **Auth**: in Supabase create the first dashboard user
   (Authentication → Users → *email/password* or magic link). Copy its **UID**.
   JWT verification auto-configures: with `SUPABASE_URL` set, the API fetches
   signing keys from `{SUPABASE_URL}/auth/v1/.well-known/jwks.json`
   (RS256/ES256); older projects can set `SUPABASE_JWT_SECRET` (HS256)
   instead. See `app/core/auth.py`.
6. **Bootstrap the first organization**:

   ```bash
   export DATABASE_URL="postgresql+asyncpg://alpha_app:<pw>@<pooler-host>/postgres"
   python -m app.db.bootstrap_org \
     --name "Alpha Estates" --slug alpha-estates \
     --owner-name "Ahmed Raza" --owner-email ahmed@example.com \
     --auth-user-id <the-supabase-user-uid>
   ```

   Uniqueness (slug, auth user id, Twilio numbers) is enforced by global DB
   constraints; a duplicate exits cleanly without writing.

## 2. Backend — Railway or Render (Docker)

Both platforms build `backend/Dockerfile` from the repo root (the image
ships `database/migrations` + `MIGRATIONS_DIR` so the same image runs
migrations).

**Render** — `render.yaml` is a complete Blueprint (New → Blueprint → select
repo). Set the prompted env vars (`DATABASE_URL`, `ADMIN_DATABASE_URL`,
`APP_DB_PASSWORD`, Twilio, OpenAI, Sentry). `preDeployCommand` runs
migrations before each deploy.

**Railway** — `railway.json` configures the Docker build + health check.
Set the same env vars in the service settings; run migrations once per
deploy via `railway run python -m app.db.migrate` (or a one-off job) if you
prefer not to automate it.

Required env (see `.env.example` for the full list):

```
ENVIRONMENT=production
DATABASE_URL=postgresql+asyncpg://alpha_app:<pw>@<host>/<db>
SUPABASE_URL=https://<ref>.supabase.co
TWILIO_ACCOUNT_SID=... TWILIO_AUTH_TOKEN=...   # webhook fails CLOSED without it
TWILIO_WEBHOOK_URL=https://<backend-public-url>/api/v1/webhooks/twilio
ALLOWED_ORIGINS=["https://<frontend-domain>"]  # CORS is an allowlist
DEFAULT_ORGANIZATION_SLUG=alpha-estates        # shared-number routing fallback
OPENAI_API_KEY=...                             # AI engine (optional but expected)
SENTRY_DSN=...                                 # optional error monitoring
```

Smoke test after deploy:

```bash
curl https://<backend>/api/v1/health          # 200 {"status":"ok","environment":"production"}
curl -i https://<backend>/api/v1/docs          # 404 — docs off in production
curl -i -X POST https://<backend>/api/v1/auth/dev-login ...   # 404 — dev auth off
```

## 3. Twilio — production messaging

1. WhatsApp Sandbox → upgrade to a production Twilio number with the
   WhatsApp API; or keep SMS for launch (same pipeline).
2. Set the org's inbound number (`organizations.twilio_whatsapp_from`) via
   the bootstrap CLI (`--twilio-whatsapp-from`) or SQL — per-org routing
   keys off it.
3. Twilio Console → Messaging → Settings → **webhook URL**:
   `https://<backend>/api/v1/webhooks/twilio` (HTTP POST). Set
   `TWILIO_WEBHOOK_URL` to the same value — signatures are computed over
   the full URL, proxies sometimes rewrite it (see
   `app/core/twilio_security.py`).
4. Verify: send a WhatsApp message to the number; the lead appears in the
   dashboard within seconds (Phase 8 realtime), and the webhook log shows a
   `200` with valid signature.

## 4. Frontend — Vercel

1. Import the repo; **Root Directory: `frontend`** (Vercel reads
   `vercel.json`; build/dev/test commands and the Next preset are automatic).
2. Set env var `BACKEND_INTERNAL_URL=https://<backend-public-url>` — the
   server-side rewrite (`next.config.ts`) proxies browser calls
   `/api/backend/*` to it. No CORS exposure, backend URL never ships to the
   client.
3. Note on SSE through the proxy: the realtime stream keeps a long-lived
   connection; Vercel's proxy supports it and our 15s keepalive pings
   prevent idle cutoffs. If you ever see proxy-induced SSE lag, point the
   dashboard at the API origin directly — set `ALLOWED_ORIGINS` on the
   backend and swap `BASE_PATH` in `frontend/lib/api.ts` to the backend URL.
4. Custom domain: Vercel → Domains. Update `ALLOWED_ORIGINS` accordingly.

Self-hosted instead: `docker compose -f docker-compose.prod.yml up -d
--build` runs db + migrate + backend + frontend on one host (health-gated;
the `migrate` one-shot must succeed before the API boots).

## 5. Go-live checklist

- [ ] `ENVIRONMENT=production` (docs off, dev-login off, webhook signature required)
- [ ] Migrations applied; `alpha_app` role exists; RLS verified
      (`SELECT count(*) FROM leads;` as `alpha_app` with no tenant GUC → 0 rows)
- [ ] First org + owner bootstrapped; Supabase user can sign in
- [ ] Twilio webhook signature verified (send a real message)
- [ ] Rate limits sized for the platform (`DEV_LOGIN_RATE_LIMIT`,
      `WEBHOOK_RATE_LIMIT` defaults are sane starts)
- [ ] `ALLOWED_ORIGINS` = exact frontend origin(s)
- [ ] Sentry DSN set (optional) + platform alerts on health-check failures
- [ ] Backups: Supabase daily PITR (free tier) — confirm schedule
- [ ] Secrets only in platform env stores; `.env` never committed

## 6. Operational notes

- **Scaling to multiple API instances:** the event bus + rate limiter are
  in-process by design (audit findings R1). Swap points are single modules
  (`app/core/events.py`, `app/core/rate_limit.py`) — Redis pub/sub and
  INCR+EXPIRE respectively. Single instance comfortably serves an MVP.
- **Zero-downtime deploys:** migrations are additive-first (new columns
  nullable, then code, then backfill) so the old revision keeps serving
  while the new one boots.
- **Client IP trust chain:** the API runs with `--proxy-headers
  --forwarded-allow-ips "*"` trusting the platform edge to append the real
  client IP to `X-Forwarded-For` — rate limiting keys on the **last** entry
  (the one the client cannot forge; see `app/core/rate_limit.py`).
