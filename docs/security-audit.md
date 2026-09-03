# Security Audit — Phase 9

**Date:** 2026-09-03 · **Scope:** entire `backend/` + `frontend/` at commit range Phase 1–8 (`c0f9983`) → Phase 9
**Method:** line-by-line review of every trust boundary (auth, webhook ingest, tenant isolation, realtime fan-out, outbound messaging), OWASP API Top-10 checklist, adversarial test suite (`tests/test_security.py`, 27 tests), dependency audit (`pip-audit`, `npm audit`), coverage measurement.

---

## 1. Result summary

| Area | Status |
|---|---|
| Dependency vulnerabilities (runtime) | **0 known** — `pip-audit` clean, `npm audit` clean (dev + prod) |
| Backend coverage | **96%** (163 tests, greenlet-aware measurement) |
| Frontend unit tests | 11/11 (SSE parser, backoff) + `tsc` + eslint + `next build` gates |
| Critical / high findings open | **0** |
| Findings fixed this phase | 5 (see §2) |
| Accepted risks (documented) | 4 (see §4) |

## 2. Findings & fixes (this phase)

| # | Finding | Severity | Fix |
|---|---|---|---|
| F1 | **No rate limiting** on public endpoints — `POST /auth/dev-login` allowed unlimited email guessing; webhook allowed request flooding | High | Sliding-window limiter per client IP: dev-login 10/min, webhook 240/min (`DEV_LOGIN_RATE_LIMIT`, `WEBHOOK_RATE_LIMIT`), HTTP 429 + `Retry-After`. Rejected attempts still count (a persistent hammer stays blocked). `app/core/rate_limit.py` |
| F2 | **Error handler stripped HTTP headers** from error responses — `Retry-After` (429) and `WWW-Authenticate` (401) never reached clients | Medium | `http_error_handler` now forwards `exc.headers` (`app/main.py`). Found by the new 429 test. |
| F3 | **No security headers** on API responses | Medium | Pure-ASGI middleware: `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, CSP `default-src 'none'; frame-ancestors 'none'`, and `Cache-Control: no-store` on all API paths (tenant data must never sit in shared caches). SSE-safe (headers injected on `response.start`; the stream body passes through untouched). Frontend mirrors the baseline + prod-only CSP in `next.config.ts`. |
| F4 | **No request body-size cap** — a single huge POST could pin memory | Medium | Declared `Content-Length` capped at `MAX_REQUEST_BODY_BYTES` (1 MiB default) → 413 before handler dispatch. |
| F5 | **Interactive docs & dev-login surface in production** | Low | `/api/v1/docs`, `/redoc`, `/openapi.json` disabled when `ENVIRONMENT=production` (was already refusing dev-login auth since Phase 3 — re-verified by test). |

Dependency findings remediated in the same pass (all post-compromise vectors, none remotely exploitable in this architecture — see advisories):

| Package | Advisory | Relevance before fix | Resolution |
|---|---|---|---|
| langgraph 0.6.11 | PYSEC-2026-83 (msgpack checkpoint deserialization → RCE) | Requires a persistent checkpointer; **we run checkpointer-free** (graph rebuilt per message) | **Upgraded to langgraph ≥1.0.10** — full suite passes on 1.2.11 |
| langchain-core 0.3.86 | PYSEC-2026-2193, -2562 | defence-in-depth | **Upgraded to ≥1.2.22** (running 1.6.1) |
| langgraph-checkpoint 3.0.1 | PYSEC-2026-2573, -2574 (pickle fallback in cache serializer) | Requires attacker write access to a cache backend we don't configure | **4.2.0** (pulled in by langgraph 1.x) |
| langgraph-sdk 0.2.15 | PYSEC-2026-2194, -2575 (URL path interpolation) | **SDK unused** — we embed langgraph, never call LangGraph server | **0.4.4** (transitive) |

`pip-audit -r requirements.txt` → **No known vulnerabilities.** `npm audit` (dev+prod) → **0**.

## 3. Controls verification (pre-existing, now test-pinned)

| Control | Evidence |
|---|---|
| Tenant isolation is a DB guarantee | RLS with `FORCE`, least-privilege `alpha_app` role, transaction-scoped GUC (`app.current_organization_id`); cross-org tests in `test_database.py`, `test_api_leads.py`, `test_realtime_api.py`, plus new SSE-fanout isolation test |
| JWT hardening | HS256 pinned (alg-confusion & `alg=none` rejected by test), `exp`+`sub` required, 10s leeway; expired/tampered/unsigned tokens → 401 (tests) |
| Twilio webhook auth | HMAC-SHA1 signature per request; **fail-closed**: production without a configured token answers 503, never accepts unsigned (test) |
| Webhook idempotency | `MessageSid` dedupe — Twilio retries ack without reprocessing (test) |
| Input validation | Pydantic at every boundary; strict form content-type (415); unknown `To` → 404, no org oracle beyond the number |
| CORS | Explicit origin allowlist; unlisted origin gets no `access-control-allow-origin` (test) |
| Secrets | Only via env/`.env` (git-ignored); `.env.example` documents each; no secret ever logged (structured logs carry ids, not tokens) |
| Prompt-injection containment | LLM output treated as data; tool requests validated by `ToolExecutor`; scorer reads only structured facts (Phase 5–6 tests) |
| Outbound sender | Exact-request tests (URL, Basic auth, payload, channel prefixes) via injected transport — no credentials in logs, no test network calls |

## 4. Accepted risks & roadmap

| # | Risk | Rationale | When |
|---|---|---|---|
| R1 | Rate limiter & event bus are in-process | Single-instance MVP by design; horizontally scaled deployments under-count per node (each node still throttles locally). Redis (`INCR`+`EXPIRE` / pub-sub) is the drop-in swap behind unchanged interfaces. | Phase 10, if scaling |
| R2 | ~~`alg` HS256 shared-secret JWTs (Supabase legacy secret)~~ | **Resolved in Phase 10**: `app/core/auth.py` now verifies Supabase JWKS (RS256/ES256, keyset cached, per-strategy algorithm pinning) with the HS256 secret as fallback; test-pinned against algorithm-confusion and wrong-key forgeries (`tests/test_auth_strategies.py`). | Closed |
| R3 | Chunked request bodies without `Content-Length` bypass F4's declared-length check | Twilio always sends a length; reverse proxies (Railway/Render/Vercel) enforce their own caps. | Accepted |
| R4 | `agents/llm.py` 61% / `db/migrate.py` 54% coverage | Live-OpenAI error paths (behind the `ScriptedLLM` seam) and the CLI migration runner (executed in every test-session bootstrap, unmeasured). No trust boundary crosses these uncovered lines. | Accepted |

## 5. Coverage

`pytest --cov=app` → **96% total** (1,986 statements). Configuration note: measurement uses
`concurrency = ["greenlet", "thread"]` — SQLAlchemy async switches greenlets, and without this
setting the C tracer silently under-reports handler bodies (webhooks.py measured 58% before, 99% after).

```
ruff check .         → clean        mypy app            → clean (75 files)
pytest --cov=app     → 163 passed, 96%
eslint / tsc / build → clean        vitest              → 11 passed
```

## 6. Regression protection

All Phase 9 controls are pinned by `tests/test_security.py` (27 tests: headers, CORS scoping,
limiter unit + endpoint behaviour incl. scope isolation and the 0-disables knob, body cap,
production lockdown, JWT forgery attempts, SSE isolation) and `tests/test_twilio_sender.py` (6 tests).
CI (`.github/workflows/ci.yml`) runs ruff + mypy + pytest-with-coverage (fail-under 90) on
Python 3.11/3.12 and eslint + vitest + build on Node 22.
