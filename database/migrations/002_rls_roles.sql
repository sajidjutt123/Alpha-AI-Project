-- 002 — runtime role, grants, Row Level Security (tenant isolation)
--
-- Model:
--   * The backend NEVER connects as the table owner / superuser.
--   * It connects as `alpha_app` (least privilege, no BYPASSRLS).
--   * Per request the backend sets `app.current_organization_id` (a
--     transaction-local GUC) and RLS enforces isolation — even if the
--     application code has a bug. Defense in depth.
--   * FORCE ROW LEVEL SECURITY: policies apply to the table owner too
--     (matters on Supabase where `postgres` owns the tables).
--
-- The literal __APP_ROLE_PASSWORD__ below is replaced by the migration
-- runner (value from APP_DB_PASSWORD; validated charset [A-Za-z0-9_-]).

-- ===========================================================================
-- Runtime role + grants
-- ===========================================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'alpha_app') THEN
        CREATE ROLE alpha_app LOGIN PASSWORD '__APP_ROLE_PASSWORD__';
    ELSE
        ALTER ROLE alpha_app LOGIN PASSWORD '__APP_ROLE_PASSWORD__';
    END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO alpha_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO alpha_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO alpha_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO alpha_app;

-- ===========================================================================
-- Tenant-context helper: NULL when unset (=> policy denies everything)
-- ===========================================================================
CREATE OR REPLACE FUNCTION current_org_id() RETURNS uuid
LANGUAGE sql STABLE PARALLEL SAFE
AS $$
    SELECT nullif(current_setting('app.current_organization_id', true), '')::uuid
$$;

-- ===========================================================================
-- Enable + FORCE RLS on every tenant table
-- ===========================================================================
ALTER TABLE organizations          ENABLE ROW LEVEL SECURITY;
ALTER TABLE agents                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE leads                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE properties             ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages               ENABLE ROW LEVEL SECURITY;
ALTER TABLE lead_property_matches  ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_runs                ENABLE ROW LEVEL SECURITY;

ALTER TABLE organizations          FORCE ROW LEVEL SECURITY;
ALTER TABLE agents                 FORCE ROW LEVEL SECURITY;
ALTER TABLE leads                  FORCE ROW LEVEL SECURITY;
ALTER TABLE properties             FORCE ROW LEVEL SECURITY;
ALTER TABLE messages               FORCE ROW LEVEL SECURITY;
ALTER TABLE lead_property_matches  FORCE ROW LEVEL SECURITY;
ALTER TABLE ai_runs                FORCE ROW LEVEL SECURITY;

-- ===========================================================================
-- Policies — directly scoped tables
-- ===========================================================================
CREATE POLICY organizations_isolation ON organizations FOR ALL
    USING (id = current_org_id())
    WITH CHECK (id = current_org_id());

CREATE POLICY agents_isolation ON agents FOR ALL
    USING (organization_id = current_org_id())
    WITH CHECK (organization_id = current_org_id());

CREATE POLICY leads_isolation ON leads FOR ALL
    USING (organization_id = current_org_id())
    WITH CHECK (organization_id = current_org_id());

CREATE POLICY properties_isolation ON properties FOR ALL
    USING (organization_id = current_org_id())
    WITH CHECK (organization_id = current_org_id());

-- ===========================================================================
-- Policies — tables scoped through their parent lead
-- ===========================================================================
CREATE POLICY messages_isolation ON messages FOR ALL
    USING (EXISTS (SELECT 1 FROM leads l
                   WHERE l.id = messages.lead_id
                     AND l.organization_id = current_org_id()))
    WITH CHECK (EXISTS (SELECT 1 FROM leads l
                        WHERE l.id = messages.lead_id
                          AND l.organization_id = current_org_id()));

CREATE POLICY matches_isolation ON lead_property_matches FOR ALL
    USING (EXISTS (SELECT 1 FROM leads l
                   WHERE l.id = lead_property_matches.lead_id
                     AND l.organization_id = current_org_id())
       AND EXISTS (SELECT 1 FROM properties p
                   WHERE p.id = lead_property_matches.property_id
                     AND p.organization_id = current_org_id()))
    WITH CHECK (EXISTS (SELECT 1 FROM leads l
                        WHERE l.id = lead_property_matches.lead_id
                          AND l.organization_id = current_org_id())
            AND EXISTS (SELECT 1 FROM properties p
                        WHERE p.id = lead_property_matches.property_id
                          AND p.organization_id = current_org_id()));

CREATE POLICY ai_runs_isolation ON ai_runs FOR ALL
    USING (EXISTS (SELECT 1 FROM leads l
                   WHERE l.id = ai_runs.lead_id
                     AND l.organization_id = current_org_id()))
    WITH CHECK (EXISTS (SELECT 1 FROM leads l
                        WHERE l.id = ai_runs.lead_id
                          AND l.organization_id = current_org_id()));
