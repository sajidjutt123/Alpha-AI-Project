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
| 4 | Webhooks | `POST /webhooks/twilio` (signature-verified, idempotent) |
| 5–6 | AI (internal) | agent pipeline invoked by workers, not public HTTP |
| 7+ | Realtime | Supabase Realtime channels (no REST) |
