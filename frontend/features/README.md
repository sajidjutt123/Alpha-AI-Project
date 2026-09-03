# Feature Modules

Dashboard features live here as self-contained modules — everything a
feature needs in one place, so `app/` stays thin (routing/layout only).

```
features/
  leads/          components + hooks + actions for the leads table & detail
  properties/     listing cards, detail views, recommendation UI
  conversations/  live chat transcript, AI status, takeover controls
  analytics/      KPI cards and charts
  auth/           login flow, session helpers
  realtime/       SSE connection provider + useRealtimeEvent hook (Phase 8)
  notifications/  notification bell, toasts, unread badge (Phase 8)
```

Convention per module:

```
features/<name>/
  components/   UI pieces specific to the feature
  hooks/        feature-specific data hooks
  <name>.ts     actions / client logic
```

Cross-feature primitives belong in `components/`; shared client logic in
`hooks/`; server/API access in `lib/`; shared contracts in `types/`.

Modules are created as their phases land (Phase 7 onward).
