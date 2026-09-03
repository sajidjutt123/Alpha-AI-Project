# API Reference

Base URL (local): `http://localhost:8000`
Versioned prefix: `/api/v1`
Interactive docs: `/api/v1/docs` (Swagger) · `/api/v1/redoc`

## Conventions

- JSON request/response bodies; Pydantic-validated on both directions
- `camelCase` in payloads is avoided — fields are `snake_case` (Python-native,
  matches the database schema)
- Errors follow FastAPI's `{"detail": ...}` shape; structured error codes land
  with Phase 3
- All dashboard endpoints require an authenticated agent (Phase 3)

## Endpoints

### Status: implemented (Phase 1)

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/health` | Liveness: `{status, version, environment, timestamp}` |

### Planned by phase

| Phase | Group | Endpoints |
|---|---|---|
| 3 | Leads | `GET/POST /leads`, `GET/PATCH /leads/{id}`, lead status transitions |
| 3 | Properties | `GET/POST /properties`, `GET /properties/{id}` |
| 3 | Agents | `GET /agents`, `GET /agents/me` |
| 3 | Analytics | `GET /analytics/overview` |
| 4 | Webhooks | `POST /webhooks/twilio` (signature-verified) |
| 5–6 | AI (internal) | agent pipeline invoked by workers, not public HTTP |
| 7+ | Realtime | Supabase Realtime channels (no REST) |
