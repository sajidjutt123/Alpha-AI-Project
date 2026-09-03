-- 003 — auth bootstrap: security-definer agent lookup
--
-- Chicken-and-egg: agents/leads are RLS-protected by tenant context, but
-- resolving WHO is calling (auth user -> agent -> organization) must happen
-- BEFORE any tenant context exists. A SECURITY DEFINER function is the
-- narrow, audited door for exactly that lookup — the pattern Supabase
-- recommends for auth bootstrap. It discloses only the caller's own row.

CREATE OR REPLACE FUNCTION app_agent_by_auth_user(p_auth_user_id uuid)
RETURNS TABLE (
    agent_id        uuid,
    organization_id uuid,
    role            agent_role,
    name            text,
    email           text,
    is_active       boolean
)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT a.id, a.organization_id, a.role, a.name, a.email, a.is_active
    FROM agents a
    WHERE a.auth_user_id = p_auth_user_id
      AND a.is_active
$$;

REVOKE ALL ON FUNCTION app_agent_by_auth_user(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_agent_by_auth_user(uuid) TO alpha_app;
