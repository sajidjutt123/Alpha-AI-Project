-- 004 — Twilio webhook routing (multi-tenant)
--
-- Inbound webhooks are unauthenticated HTTP (validated by Twilio signature,
-- not by our JWTs), so tenant routing must work WITHOUT any bound tenant
-- context. SECURITY DEFINER lookups are the narrow door for that, same
-- pattern as 003.

ALTER TABLE organizations
    ADD COLUMN IF NOT EXISTS twilio_whatsapp_from text,
    ADD COLUMN IF NOT EXISTS twilio_sms_from text;

CREATE UNIQUE INDEX IF NOT EXISTS uq_organizations_twilio_whatsapp_from
    ON organizations (twilio_whatsapp_from) WHERE twilio_whatsapp_from IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_organizations_twilio_sms_from
    ON organizations (twilio_sms_from) WHERE twilio_sms_from IS NOT NULL;

-- Route an inbound `To` number to its owning organization.
-- (Partial unique indexes keep numbers unique per channel; in practice the
-- whatsapp: prefix and bare E.164 formats never collide across columns.)
CREATE OR REPLACE FUNCTION app_org_id_by_twilio_to(p_to text)
RETURNS TABLE (organization_id uuid)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT id FROM organizations
    WHERE twilio_whatsapp_from = p_to
       OR twilio_sms_from = p_to
    LIMIT 1
$$;

-- Fallback routing for single-tenant/sandbox deployments (shared number).
CREATE OR REPLACE FUNCTION app_org_id_by_slug(p_slug text)
RETURNS TABLE (organization_id uuid)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT id FROM organizations WHERE slug = p_slug LIMIT 1
$$;

REVOKE ALL ON FUNCTION app_org_id_by_twilio_to(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app_org_id_by_slug(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_org_id_by_twilio_to(text) TO alpha_app;
GRANT EXECUTE ON FUNCTION app_org_id_by_slug(text) TO alpha_app;
