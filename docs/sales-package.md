# Alpha AI — Sales Package (Phase 11)

*AI Real-Estate Lead Qualification & Sales Automation — built for
Pakistani agencies, architected like enterprise SaaS.*

---

## 1. One-liner

> **Alpha AI turns your WhatsApp queue into a qualified, prioritized,
> property-matched sales pipeline — replying in seconds, 24/7, in the
> way DHA and Bahria buyers actually message.**

## 2. The problem (the prospect's own words)

- "Leads message at night; we reply next day and they've gone elsewhere."
- "We can't tell which of 200 WhatsApp chats is worth calling first."
- "Junior agents waste hours asking budget/location/type the AI could
  collect in two minutes."
- "Our listings live in Excel; nobody matches them to buyers."

Speed-to-lead is the whole game in Pakistani real estate: the first
credible response usually wins the site visit.

## 3. The product, mapped to that pain

| Pain | Alpha AI capability | Where it shows in the demo |
|---|---|---|
| Slow after-hours replies | WhatsApp/SMS webhook → AI replies in seconds, 24/7 | live lead moment (`demo.py flow`) |
| No prioritization | deterministic 0–100 score (budget 25 / location 20 / urgency 20 / requirements 20 / engagement 15), HOT ≥80 / WARM ≥50 | Ali Hassan, 82 HOT |
| Manual qualification | LLM extracts budget (crore/lakh → PKR), location, type, bedrooms, urgency into structured fields | lead detail, extracted requirements |
| Inventory blindness | property matching with explainable reasons (budget 40 / location 25 / type 15 / bedrooms 20 + affordability gates) | matched-properties cards |
| Dropped handoffs | frustration/human-request detection → HANDOFF alert + one-click takeover | bell + composer |
| No visibility | agent command center: KPIs, Kanban, transcripts, live realtime board | the dashboard |

## 4. Ideal customer profile

- Real-estate agencies & developers in Pakistan, **3–50 agents**
- Markets: DHA (Lahore/Karachi/Islamabad), Bahria Town, Gulberg, DHA
  Multan-style secondary cities
- Volume: **100–1,000 inbound WhatsApp leads/month**
- Already advertising on Facebook/Instagram/Zameen → paying for leads
  that currently die in the inbox
- Decision maker: owner or sales head; technical buyer optional
  (we deploy it for them)

## 5. ROI math (fill in the prospect's numbers live)

Worked example — a 10-agent Lahore agency:

| Input | Value |
|---|---|
| Inbound WhatsApp leads / month | 300 |
| After-hours / weekend share | 40% (120 leads) |
| Current after-hours reply rate | ~0% |
| Deals per contacted lead (industry) | 4% |
| Average commission per deal | PKR 800,000 (1% of an 80-lakh sale) |

- Recovered after-hours conversations that convert: 120 × 4% ≈ **5 deals/mo**
- Even at half that: **PKR 2,000,000/mo in recovered commissions** for a
  tool priced at a fraction of it (see §6).
- Second-order savings: ~15 agent-hours/day of qualification work; instant
  ramp for new agents (the AI asks, the agent closes).

> Rule of thumb to say out loud: **"One recovered deal per month pays for
> the whole platform for a year."**

## 6. Pricing (suggested launch structure)

| Plan | For | Price (PKR/mo) | Includes |
|---|---|---|---|
| **Starter** | 1 number, 3 agents | 24,900 | AI qualification + dashboard + 500 AI conversations |
| **Growth** | ≤10 agents, 2 numbers | 59,900 | + property matching, realtime alerts, analytics |
| **Enterprise** | agencies/developers | custom | + multi-org, SSO, SLA, on-prem option |

- Platform costs (Twilio WhatsApp, OpenAI, hosting ≈ $50–150/mo at this
  scale) are passed through at cost, itemized — no markup, full transparency.
- Annual prepay: 2 months free. Setup + onboarding: PKR 50,000 one-time
  (numbers, listings import, prompt tuning to the agency's tone).

## 7. Why us — the defensible differences

1. **Deterministic, explainable scoring** — the LLM never owns business
   logic: validated tools, deterministic Python scoring/matching, audit
   trail per decision. Agents can defend "why 82" to a client.
2. **Multi-tenant with database-enforced isolation** — Row Level Security,
   least-privilege DB role; a second agency can share the platform with a
   *database guarantee* of zero leakage. Most local competitors are
   single-tenant scripts.
3. **Realtime command center** — SSE event bus: leads land on the board
   with alerts while they happen; not a morning report.
4. **Security-audited, zero known CVEs** — `docs/security-audit.md`:
   rate limiting, JWT strategy matrix (incl. forgery tests), Twilio
   signature fail-closed, 95% test coverage.
5. **Own your stack** — runs on the customer's Twilio, OpenAI, Supabase
   accounts (Docker/Vercel/Railway-ready). No data hostage situation.

## 8. Objection handling

| Objection | Response |
|---|---|
| "AI will scare off my clients" | The AI asks one question at a time, in the agency's tone, and hands to a human the moment the buyer asks — takeover is one click, with full context. |
| "WhatsApp is informal for 3-crore deals" | Exactly why speed + structure wins: the AI qualifies, the human closes. All conversation history stays attached to the lead. |
| "We already have a CRM" | Alpha AI feeds CRMs (export/API) — it sits where deals are won: the first five minutes of a WhatsApp chat. |
| "Is my data safe?" | Your own Postgres/Supabase, RLS-isolated per agency, secrets in platform vaults, audited codebase. We can deploy inside your cloud. |
| "What if the AI hallucinates prices?" | It can't — it only matches listings from your verified inventory; every number shown comes from the database, never the model. |
| "Urdu/Roman Urdu?" | The pipeline handles mixed English/Roman-Urdu phrasing common in DHA/Bahria chats; full localization is on the roadmap. |
| "Too expensive" | One recovered deal/month covers a year (§5). You're currently paying for leads that die in the inbox. |

## 9. Proof assets to hand over

- **Live demo** — `docs/demo-script.md` (8 minutes, runs on a laptop)
- **Security audit** — `docs/security-audit.md` (findings, fixes, 0 CVEs)
- **Architecture** — `docs/architecture.md` (event bus, RLS, AI pipeline)
- **API reference** — `docs/api.md` (clean REST + SSE contract)
- This repo: 175 backend tests / 95% coverage, CI-gated lint + types

## 10. Implementation timeline (what buying looks like)

| Day | Milestone |
|---|---|
| 0 | Demo + choose plan; sign-off on pricing/ROI numbers |
| 1–2 | Provision: Twilio WhatsApp number, OpenAI, Supabase; deploy (docs/deployment.md) |
| 3–4 | Onboarding: listings import, tone/prompt tuning, agent accounts, RLS verified |
| 5 | Go-live: Twilio webhook switched on; first week of realtime alerts |
| 14 | Checkpoint: score-threshold tuning from real conversations |
| 30 | Business review: speed-to-lead, conversion, recovered-deals report |

## 11. Roadmap (say "what's next", not "what's missing")

- CSV/bulk listings import + public listing pages
- Scheduled follow-ups (AI re-engages cold WARM leads)
- Urdu-first conversation flows
- Call-log integration + voice notes transcription
- Multi-number routing per market (Lahore/Karachi/Islamabad teams)
