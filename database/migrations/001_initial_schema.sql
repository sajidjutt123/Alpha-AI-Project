-- 001 — extensions, enums, tables, triggers, indexes
-- Multi-tenant schema: every domain table is scoped by organization_id.
-- Applied once (tracked in schema_migrations); canonical source of truth.

-- ===========================================================================
-- Enums
-- ===========================================================================
CREATE TYPE lead_status AS ENUM ('NEW', 'CONTACTED', 'QUALIFIED', 'CONVERTED', 'LOST');
CREATE TYPE lead_intent AS ENUM ('BUY', 'SELL', 'RENT', 'GENERAL_INQUIRY', 'HUMAN_AGENT', 'UNKNOWN');
CREATE TYPE sender_type AS ENUM ('CUSTOMER', 'AI', 'AGENT', 'SYSTEM');
CREATE TYPE message_channel AS ENUM ('WHATSAPP', 'SMS', 'DASHBOARD');
CREATE TYPE property_type AS ENUM ('HOUSE', 'APARTMENT', 'PLOT', 'COMMERCIAL');
CREATE TYPE property_availability AS ENUM ('AVAILABLE', 'RESERVED', 'SOLD', 'RENTED');
CREATE TYPE agent_role AS ENUM ('OWNER', 'ADMIN', 'AGENT');

-- ===========================================================================
-- organizations — SaaS tenants (one row per real-estate company)
-- ===========================================================================
CREATE TABLE organizations (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name        text NOT NULL,
    slug        text NOT NULL UNIQUE,
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- ===========================================================================
-- agents — team members; credentials live in Supabase Auth (auth_user_id)
-- ===========================================================================
CREATE TABLE agents (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations (id) ON DELETE CASCADE,
    name            text NOT NULL,
    email           text NOT NULL,
    phone           text,
    role            agent_role NOT NULL DEFAULT 'AGENT',
    auth_user_id    uuid UNIQUE,          -- Supabase Auth user (auth.users.id)
    is_active       boolean NOT NULL DEFAULT true,
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, email)
);

-- ===========================================================================
-- leads — prospects with qualification state
-- ===========================================================================
CREATE TABLE leads (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     uuid NOT NULL REFERENCES organizations (id) ON DELETE CASCADE,
    name                text,
    phone               text NOT NULL,
    email               text,
    status              lead_status NOT NULL DEFAULT 'NEW',
    intent              lead_intent,
    budget_min          bigint,
    budget_max          bigint,
    preferred_location  text,
    property_type       property_type,
    bedrooms            integer,
    urgency_score       integer,          -- 1..10 (AI-assessed)
    qualification_score integer,          -- 0..100 (deterministic scoring, Phase 5)
    summary             text,             -- AI conversation summary
    assigned_agent_id   uuid REFERENCES agents (id) ON DELETE SET NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, phone),      -- lead identity for webhook routing
    CONSTRAINT leads_budget_range CHECK (budget_min IS NULL OR budget_max IS NULL
                                         OR budget_min <= budget_max),
    CONSTRAINT leads_bedrooms_positive CHECK (bedrooms IS NULL OR bedrooms > 0),
    CONSTRAINT leads_urgency_range CHECK (urgency_score IS NULL
                                          OR urgency_score BETWEEN 1 AND 10),
    CONSTRAINT leads_qualification_range CHECK (qualification_score IS NULL
                                                OR qualification_score BETWEEN 0 AND 100)
);

-- ===========================================================================
-- messages — full conversation transcript per lead
-- ===========================================================================
CREATE TABLE messages (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id             uuid NOT NULL REFERENCES leads (id) ON DELETE CASCADE,
    sender_type         sender_type NOT NULL,
    content             text NOT NULL,
    channel             message_channel NOT NULL,
    external_message_id text UNIQUE,      -- Twilio SID (idempotent webhooks)
    created_at          timestamptz NOT NULL DEFAULT now()
);

-- ===========================================================================
-- properties — listings catalogue (prices in PKR)
-- ===========================================================================
CREATE TABLE properties (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations (id) ON DELETE CASCADE,
    title           text NOT NULL,
    description     text,
    price           bigint NOT NULL,
    location        text NOT NULL,
    property_type   property_type NOT NULL,
    bedrooms        integer,
    bathrooms       integer,
    area            integer,              -- square feet
    availability    property_availability NOT NULL DEFAULT 'AVAILABLE',
    image_url       text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT properties_price_positive CHECK (price > 0),
    CONSTRAINT properties_area_positive CHECK (area IS NULL OR area > 0)
);

-- ===========================================================================
-- lead_property_matches — AI recommendations with explanation
-- ===========================================================================
CREATE TABLE lead_property_matches (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id     uuid NOT NULL REFERENCES leads (id) ON DELETE CASCADE,
    property_id uuid NOT NULL REFERENCES properties (id) ON DELETE CASCADE,
    match_score integer NOT NULL,
    reason      text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (lead_id, property_id),
    CONSTRAINT matches_score_range CHECK (match_score BETWEEN 0 AND 100)
);

-- ===========================================================================
-- ai_runs — execution telemetry (debugging + cost analysis)
-- ===========================================================================
CREATE TABLE ai_runs (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id        uuid NOT NULL REFERENCES leads (id) ON DELETE CASCADE,
    model          text NOT NULL,
    prompt_version text NOT NULL,
    input_tokens   integer NOT NULL DEFAULT 0,
    output_tokens  integer NOT NULL DEFAULT 0,
    latency_ms     integer NOT NULL DEFAULT 0,
    created_at     timestamptz NOT NULL DEFAULT now()
);

-- ===========================================================================
-- updated_at trigger
-- ===========================================================================
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_leads_set_updated_at
    BEFORE UPDATE ON leads
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ===========================================================================
-- Indexes (hot paths)
-- ===========================================================================
CREATE INDEX idx_leads_org_status     ON leads (organization_id, status);
CREATE INDEX idx_leads_org_created    ON leads (organization_id, created_at DESC);
CREATE INDEX idx_leads_assigned_agent ON leads (assigned_agent_id)
    WHERE assigned_agent_id IS NOT NULL;
CREATE INDEX idx_messages_lead_created ON messages (lead_id, created_at);
CREATE INDEX idx_properties_org_type     ON properties (organization_id, property_type);
CREATE INDEX idx_properties_org_price    ON properties (organization_id, price);
CREATE INDEX idx_properties_org_location ON properties (organization_id, location);
CREATE INDEX idx_matches_lead  ON lead_property_matches (lead_id);
CREATE INDEX idx_ai_runs_lead  ON ai_runs (lead_id, created_at);
