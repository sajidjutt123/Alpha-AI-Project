-- 005 — dev-login lookup: agent by email (unauthenticated bootstrap)
--
-- The dashboard login (local/dev) posts an email; the backend resolves it
-- to an active agent with a linked auth user, then mints a dev token. In
-- production the frontend uses Supabase Auth instead and this function is
-- never reached (the endpoint refuses in ENVIRONMENT=production).

CREATE OR REPLACE FUNCTION app_agent_by_email(p_email text)
RETURNS TABLE (
    agent_id        uuid,
    organization_id uuid,
    role            agent_role,
    name            text,
    email           text,
    auth_user_id    uuid
)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT a.id, a.organization_id, a.role, a.name, a.email, a.auth_user_id
    FROM agents a
    WHERE a.email = p_email
      AND a.is_active
      AND a.auth_user_id IS NOT NULL
    LIMIT 1
$$;

REVOKE ALL ON FUNCTION app_agent_by_email(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_agent_by_email(text) TO alpha_app;
