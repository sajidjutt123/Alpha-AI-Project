# API Reference

Base URL (local): `http://localhost:8000`
Versioned prefix: `/api/v1`
Interactive docs: `/api/v1/docs` (Swagger) · `/api/v1/redoc`

## Authentication

All dashboard endpoints require a bearer token (Supabase Auth JWT in
production; dev/test tokens via `AUTH_DEV_SECRET`, see `app.core.auth`):

```
Authorization: Bearer <token>
```

The token's `sub` claim is resolved to an active `agents` row (via a
SECURITY DEFINER lookup), which fixes the organization; every subsequent
query in the request runs inside that tenant's Row Level Security context.

- `401` missing/invalid/expired token
- `403` valid token but the user is not an active agent

## Conventions

- JSON bodies; `snake_case` field names (mirrors the database schema)
- Errors use one envelope:
  `{"error": {"code": "<machine-readable>", "message": "<human-readable>"}}`
  — e.g. `not_found` (404), `conflict` (409),
  `business_rule_violation` (422), `http_401`
- List endpoints return `{"items": [...], "total", "limit", "offset"}`
- Enums are uppercase strings (`NEW`, `HOUSE`, `WHATSAPP`, …)

## Endpoints

### System (public)

| Method | Path | Description |
|---|---|---|
| GET | `/health` | `{status, version, environment, timestamp}` |

### Leads

| Method | Path | Description |
|---|---|---|
| GET | `/leads` | List (filters: `status`, `q` on name/phone/location; `limit`≤100, `offset`) |
| POST | `/leads` | Create — 409 if phone already has a lead in this org |
| GET | `/leads/{id}` | Detail: lead + full transcript + matched properties (with scores/reasons) |
| PATCH | `/leads/{id}` | Partial update; `status` validated against transition rules, `assigned_agent_id` must be an org agent |

Status transitions (business rule, `422 business_rule_violation` otherwise):

```
NEW      → CONTACTED | QUALIFIED | LOST
CONTACTED→ NEW | QUALIFIED | LOST
QUALIFIED→ CONTACTED | CONVERTED | LOST
CONVERTED→ (terminal)
LOST     → NEW | CONTACTED          (re-engagement)
```

### Properties

| Method | Path | Description |
|---|---|---|
| GET | `/properties` | Search: `property_type`, `location` (ilike), `price_min/max`, `bedrooms_min` + pagination |
| POST | `/properties` | Create listing |
| GET | `/properties/{id}` | Fetch one |

### Agents

| Method | Path | Description |
|---|---|---|
| GET | `/agents/me` | Caller's agent profile + organization |
| GET | `/agents` | Active agents of the organization |

### Analytics

| Method | Path | Description |
|---|---|---|
| GET | `/analytics/overview` | totals, by-status, hot/warm/cold (80/50 thresholds), conversion rate, avg score, new-7d, property count |

### Planned by phase

| Phase | Group | Endpoints |
|---|---|---|
| 7+ | Realtime | Supabase Realtime channels (no REST) |

## Webhooks

### `POST /api/v1/webhooks/twilio` (Phase 4)

Inbound WhatsApp/SMS from Twilio — `application/x-www-form-urlencoded`,
authenticated by the **Twilio signature** (`X-Twilio-Signature`, HMAC-SHA1
over the request URL + sorted form params), not by a bearer token.

Pipeline (returns `200` with empty TwiML in milliseconds):

```
verify signature → route `To` number → organization
  → identify lead by phone (get-or-create, ProfileName captured)
  → store message (idempotent on MessageSid; retries acked, not reprocessed)
  → enqueue AI processing (background) → 200
```

Behaviour:

| Case | Result |
|---|---|
| Valid message | `200` TwiML, lead + message stored, job enqueued |
| Duplicate `MessageSid` (Twilio retry) | `200`, ignored |
| Delivery receipt / status callback (no Body) | `200`, ignored |
| Bad/missing signature (token configured) | `403` |
| `To` number not routed & no default slug | `404 not_found` |
| Production without `TWILIO_AUTH_TOKEN` | `503` (refuses unsigned traffic) |

Routing (migration 004): each organization owns its numbers
(`organizations.twilio_whatsapp_from` / `twilio_sms_from`, unique). Shared
number / sandbox deployments set `DEFAULT_ORGANIZATION_SLUG` as fallback.
Outbound replies go out on the channel the customer last used (WhatsApp by
default) via the configured sender — Twilio REST when credentials exist, a
console sender in dev.
