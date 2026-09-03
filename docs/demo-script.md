# Demo Script — Alpha AI Live Walkthrough (Phase 11)

**Format:** 8–10 minutes, screen-shared, one browser tab + one terminal.
**Story arc:** "a WhatsApp lead arrives after hours → the AI qualifies and
matches while the team sleeps → the agent wakes up to a prioritized board."

---

## Pre-demo checklist (5 minutes before)

```bash
# 1. stack up (backend on :8000, dashboard on :3000)
cd backend && AUTH_DEV_SECRET=... DATABASE_URL=... \
  .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
cd frontend && npm run dev   # or the standalone production build

# 2. restore the curated demo board (idempotent)
cd backend && DATABASE_URL=... .venv/bin/python scripts/demo.py reset

# 3. browser: http://localhost:3000/login → dev sign-in
#    ahmed@alphaestates.pk   (Owner — Alpha Estates, Lahore)
```

- [ ] Board shows the full funnel: NEW 1 · CONTACTED 3 · QUALIFIED 1 · CONVERTED 1 · LOST 1
- [ ] Live badge in the header is green ("Live")
- [ ] Terminal ready in `backend/` for `python scripts/demo.py flow`
- [ ] Zoom ≥125%, dark room? boost screen brightness
- [ ] With `OPENAI_API_KEY` set the AI replies live; without it, say so
      honestly and lean on the ingest→realtime moment (still lands)

## The board you are demoing (source of truth)

| Lead | Score | Status | The story you tell |
|---|---|---|---|
| Ali Hassan | **82 HOT** | CONTACTED | the star: full transcript, extraction, matches |
| Ayesha Malik | 91 | CONVERTED | the success story — closed from a WhatsApp lead |
| Urgent Buyer | 76 | CONTACTED | warming up, needs a nudge today |
| Match Demo | 80 | CONTACTED | property-match showcase |
| Sara Ahmed | 61 | QUALIFIED | mid-funnel, agent working it |
| Bilal Cheema | 45 COLD | LOST | went quiet — AI stopped spending time on him |
| Demo Buyer | — | NEW | fresh inbound, pipeline hasn't qualified yet |

8 listings across DHA Lahore / Bahria Town / Gulberg (PKR 1.4–3.25 crore).

---

## Minute-by-minute

### 0:00 — The problem (no screen, just you)
> "Real-estate teams in Pakistan lose deals in the WhatsApp queue. A buyer
> messages at 9:40 pm about a 3-crore DHA house; the agent replies next
> morning; the buyer already spoke to three other agencies. Alpha AI
> answers in seconds, qualifies with a deterministic score, and matches the
> buyer to actual inventory — 24/7."

### 0:30 — Login + Overview (`/dashboard`)
Sign in as `ahmed@alphaestates.pk`. Point at KPI cards: total leads, hot
count, **14% conversion**, avg score, new-this-week.
> "This is last night, summarized. The AI already triaged everything."

### 1:15 — The Kanban (`/dashboard/leads`)
Every column populated; cards carry score bars (HOT red / WARM amber /
COLD grey). Drag **Sara Ahmed** from QUALIFIED toward NEW →
> "The backend enforces legal transitions — watch it snap back."
(it 422s and the card returns: business rules live server-side, not in the UI.)

### 2:00 — The star lead (click **Ali Hassan**, score 82)
Walk down the page:
1. **Transcript** — WhatsApp bubbles (customer / AI / agent color-coded)
2. **Extracted requirements** — budget, location, type, bedrooms, urgency
   > "The AI reads crore/lakh talk and stores structured PKR facts."
3. **Score breakdown** — budget 25 / location 20 / urgency 20 /
   requirements 20 / engagement 15 → 82 = HOT
   > "Deterministic arithmetic, not vibes — auditable, configurable."
4. **Matched properties** — scored cards with reasons
   > "DHA Phase 6 House, 77% — budget fits, location exact, bedrooms off
   > by one. The AI never invents listings; it matches real inventory."

### 4:00 — 🎯 THE MOMENT (live lead, realtime)
Keep the board open. Switch to the terminal:

```bash
python scripts/demo.py flow
```

Narrate over the 4 turns (~12s): the customer is a cash buyer for DHA
Phase 6, 3.5 crore, before Eid, wants a call after Asr. On screen:
- **Toast** slides in: "New lead: +92333 4555019 9"
- **Bell badge** bumps to 1
- **Board** auto-refreshes — the lead lands in NEW *with no reload*
- Open the lead → send turns 2–4 keep arriving in the transcript live

> "Nobody touched this browser. That's a Server-Sent Events stream with
> per-organization isolation — the same event bus that powers the
> hot-lead alert when a score crosses 80."

(With `OPENAI_API_KEY` set: each turn also gets the AI's reply and the
score/matches update live — say "watch the score climb" instead.)

### 6:00 — Agent takeover (still on the live lead)
Type in the composer: *"Salam, Ahmed here — I'll call you after Asr
with two options in Phase 6."* → Send.
> "One click from AI to human. The message stores on the DASHBOARD channel
> and delivers on WhatsApp; status auto-moves NEW → CONTACTED."

### 6:45 — Notifications
Open the bell: NEW_LEAD from the live moment, mark-all-read.
> "Every agent has their own read state. HOT_LEAD and HANDOFF alerts fire
> at the exact domain moment — score crossing 80, or a frustrated buyer
> asking for a human. Miss it on screen? Enable browser notifications."

### 7:15 — Properties (`/dashboard/properties`)
Filter by location "DHA". 8 listings, PKR crore prices.
> "Your inventory, the same data the matcher uses. CSV import and a
> public-facing listing site are on the roadmap."

### 7:45 — Close (the 3 anchors)
1. **Speed to lead: seconds, 24/7** — the WhatsApp queue becomes a
   qualified, prioritized pipeline.
2. **Deterministic, explainable AI** — scores and matches your agents can
   defend to a client; the LLM never owns business logic.
3. **Enterprise-grade under the hood** — multi-tenant with database-level
   isolation (RLS), audited (see docs/security-audit.md), deploys on
   Vercel + Railway/Render + Supabase with your own Twilio/OpenAI keys.

Then: hand over `docs/sales-package.md` for pricing/ROI.

---

## Fallbacks

| If… | Do |
|---|---|
| SSE tab not updating | refresh once; the badge/toast will still be in the bell dropdown |
| No `OPENAI_API_KEY` | script already covers it — the ingest→realtime moment carries the demo |
| Webhook 404 | `To` number must be the org's `whatsapp:+14155238886` (`demo.py flow` default) |
| Wrong board state | `python scripts/demo.py reset` (idempotent, also removes demo-flow leads) |
| Someone asks about security | open `docs/security-audit.md`: RLS, rate limiting, JWT strategy matrix, 0 CVEs |

## Demo Q&A crib

- **"Does it work with SMS?"** — same pipeline; channel is per message (WhatsApp prefix detection).
- **"Can two agencies share it?"** — it's multi-tenant from day one; orgs never see each other's rows (a database guarantee, not app code).
- **"What if the AI gets it wrong?"** — it can't write: tools are validated, scoring/matching are deterministic Python, and humans take over in one click.
- **"Urdu?"** — the prompts handle Roman Urdu/English mixes common in DHA/Bahria inquiries; fully localized flows are on the roadmap.
- **"Who owns the data?"** — you do; your Postgres/Supabase, your Twilio, your OpenAI account.
