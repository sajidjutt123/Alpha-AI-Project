"""Lead API tests: CRUD, pagination, transitions, tenant isolation."""

from typing import Any

from fastapi import status
from fastapi.testclient import TestClient

from tests.conftest import OrgContext


def _lead_payload(phone: str, **overrides: Any) -> dict[str, Any]:
    return {"phone": phone, "name": "New Lead", **overrides}


class TestLeadCrud:
    def test_create_and_get_lead(self, client: TestClient, org_context: OrgContext) -> None:
        created = client.post(
            "/api/v1/leads",
            json=_lead_payload(
                "+923111122333",
                budget_min=10_000_000,
                budget_max=20_000_000,
                preferred_location="DHA Lahore",
                bedrooms=4,
            ),
            headers=org_context.headers,
        )
        assert created.status_code == status.HTTP_201_CREATED
        body = created.json()
        assert body["status"] == "NEW"
        assert body["budget_max"] == 20_000_000

        detail = client.get(f"/api/v1/leads/{body['id']}", headers=org_context.headers)
        assert detail.status_code == status.HTTP_200_OK
        assert detail.json()["phone"] == "+923111122333"

    def test_duplicate_phone_conflicts(self, client: TestClient, org_context: OrgContext) -> None:
        phone = org_context.leads[0].phone
        response = client.post(
            "/api/v1/leads", json=_lead_payload(phone), headers=org_context.headers
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json()["error"]["code"] == "conflict"

    def test_invalid_phone_rejected(self, client: TestClient, org_context: OrgContext) -> None:
        response = client.post(
            "/api/v1/leads",
            json=_lead_payload("not-a-phone"),
            headers=org_context.headers,
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_list_paginates_and_filters(self, client: TestClient, org_context: OrgContext) -> None:
        page = client.get("/api/v1/leads", headers=org_context.headers)
        assert page.status_code == status.HTTP_200_OK
        body = page.json()
        assert body["total"] == len(org_context.leads)
        assert len(body["items"]) == len(org_context.leads)
        assert body["limit"] == 50 and body["offset"] == 0

        filtered = client.get(
            "/api/v1/leads", params={"status": "NEW"}, headers=org_context.headers
        )
        assert filtered.json()["total"] == 1
        assert filtered.json()["items"][0]["status"] == "NEW"

        searched = client.get("/api/v1/leads", params={"q": "ali"}, headers=org_context.headers)
        assert searched.json()["total"] == 1
        assert searched.json()["items"][0]["name"] == "Ali Hassan"

        paged = client.get(
            "/api/v1/leads", params={"limit": 2, "offset": 2}, headers=org_context.headers
        )
        assert len(paged.json()["items"]) == len(org_context.leads) - 2

    def test_detail_includes_transcript_and_matches(
        self, client: TestClient, org_context: OrgContext
    ) -> None:
        lead_id = org_context.leads[0].id
        response = client.get(f"/api/v1/leads/{lead_id}", headers=org_context.headers)

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert next(m["content"] for m in body["messages"]) == "I need a house in DHA."
        assert body["matched_properties"][0]["match_score"] == 82
        assert body["matched_properties"][0]["title"] == "DHA Phase 6 House"

    def test_patch_updates_fields(self, client: TestClient, org_context: OrgContext) -> None:
        lead_id = org_context.leads[3].id
        response = client.patch(
            f"/api/v1/leads/{lead_id}",
            json={"name": "Now Named", "preferred_location": "Bahria Town, Lahore"},
            headers=org_context.headers,
        )

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["name"] == "Now Named"
        assert body["preferred_location"] == "Bahria Town, Lahore"


class TestStatusTransitions:
    def test_legal_transitions_allowed(self, client: TestClient, org_context: OrgContext) -> None:
        lead_id = org_context.leads[3].id  # NEW
        for target in ("CONTACTED", "QUALIFIED", "CONVERTED"):
            response = client.patch(
                f"/api/v1/leads/{lead_id}",
                json={"status": target},
                headers=org_context.headers,
            )
            assert response.status_code == status.HTTP_200_OK, response.text
            assert response.json()["status"] == target

    def test_skip_transition_rejected(self, client: TestClient, org_context: OrgContext) -> None:
        lead_id = org_context.leads[3].id  # NEW -> CONVERTED is illegal
        response = client.patch(
            f"/api/v1/leads/{lead_id}", json={"status": "CONVERTED"}, headers=org_context.headers
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        body = response.json()
        assert body["error"]["code"] == "business_rule_violation"
        assert "NEW -> CONVERTED" in body["error"]["message"]

    def test_converted_is_terminal(self, client: TestClient, org_context: OrgContext) -> None:
        lead_id = org_context.leads[2].id  # CONVERTED
        response = client.patch(
            f"/api/v1/leads/{lead_id}", json={"status": "CONTACTED"}, headers=org_context.headers
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_lost_can_reopen(self, client: TestClient, org_context: OrgContext) -> None:
        lead_id = org_context.leads[3].id  # NEW -> LOST -> CONTACTED
        lost = client.patch(
            f"/api/v1/leads/{lead_id}", json={"status": "LOST"}, headers=org_context.headers
        )
        assert lost.json()["status"] == "LOST"

        reopened = client.patch(
            f"/api/v1/leads/{lead_id}", json={"status": "CONTACTED"}, headers=org_context.headers
        )
        assert reopened.status_code == status.HTTP_200_OK
        assert reopened.json()["status"] == "CONTACTED"


class TestAssignment:
    def test_assign_teammate(self, client: TestClient, org_context: OrgContext) -> None:
        lead_id = org_context.leads[3].id
        response = client.patch(
            f"/api/v1/leads/{lead_id}",
            json={"assigned_agent_id": str(org_context.teammate.id)},
            headers=org_context.headers,
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["assigned_agent_id"] == str(org_context.teammate.id)

    def test_assign_foreign_agent_rejected(
        self, client: TestClient, org_context: OrgContext, other_org_context: OrgContext
    ) -> None:
        lead_id = org_context.leads[3].id
        foreign = other_org_context.owner.id
        response = client.patch(
            f"/api/v1/leads/{lead_id}",
            json={"assigned_agent_id": str(foreign)},
            headers=org_context.headers,
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestTenantIsolationOverHttp:
    def test_other_org_lead_is_404(
        self, client: TestClient, org_context: OrgContext, other_org_context: OrgContext
    ) -> None:
        victim = other_org_context.leads[0].id
        response = client.get(f"/api/v1/leads/{victim}", headers=org_context.headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["error"]["code"] == "not_found"

    def test_other_org_leads_invisible_in_list(
        self, client: TestClient, org_context: OrgContext, other_org_context: OrgContext
    ) -> None:
        body = client.get("/api/v1/leads", headers=org_context.headers).json()
        visible_ids = {item["id"] for item in body["items"]}
        assert visible_ids == {str(lead.id) for lead in org_context.leads}
