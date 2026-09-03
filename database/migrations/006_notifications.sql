-- 006 — notifications (dashboard alerts, per-agent read state)
--
-- Org-broadcast notifications with per-agent read tracking in a single
-- `read_by uuid[]` column: unread for agent A = rows where NOT (A = ANY(read_by)).
-- RLS: organization-scoped like every other domain table.

CREATE TABLE notifications (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations (id) ON DELETE CASCADE,
    lead_id         uuid REFERENCES leads (id) ON DELETE CASCADE,
    type            text NOT NULL,             -- NEW_LEAD | HANDOFF | HOT_LEAD
    title           text NOT NULL,
    body            text,
    read_by         uuid[] NOT NULL DEFAULT '{}',
    created_at      timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications FORCE ROW LEVEL SECURITY;

CREATE POLICY notifications_isolation ON notifications FOR ALL
    USING (organization_id = current_org_id())
    WITH CHECK (organization_id = current_org_id());

CREATE INDEX idx_notifications_org_created ON notifications (organization_id, created_at DESC);
