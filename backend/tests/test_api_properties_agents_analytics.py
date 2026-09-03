"""Property & agent/analytics API tests."""

from fastapi import status
from fastapi.testclient import TestClient

from tests.conftest import OrgContext


class TestProperties:
    def test_create_and_fetch(self, client: TestClient, org_context: OrgContext) -> None:
        payload = {
            "title": "1 Kanal House — Bahria",
            "price": 65_000_000,
            "location": "Bahria Town, Lahore",
            "property_type": "HOUSE",
            "bedrooms": 5,
            "bathrooms": 6,
            "area": 4500,
        }
        created = client.post("/api/v1/properties", json=payload, headers=org_context.headers)
        assert created.status_code == status.HTTP_201_CREATED
        body = created.json()
        assert body["availability"] == "AVAILABLE"

        fetched = client.get(f"/api/v1/properties/{body['id']}", headers=org_context.headers)
        assert fetched.status_code == status.HTTP_200_OK
        assert fetched.json()["price"] == 65_000_000

    def test_search_filters(self, client: TestClient, org_context: OrgContext) -> None:
        houses = client.get(
            "/api/v1/properties",
            params={"property_type": "HOUSE"},
            headers=org_context.headers,
        )
        assert houses.json()["total"] >= 1
        assert all(p["property_type"] == "HOUSE" for p in houses.json()["items"])

        cheap = client.get(
            "/api/v1/properties",
            params={"price_max": 20_000_000},
            headers=org_context.headers,
        )
        assert all(p["price"] <= 20_000_000 for p in cheap.json()["items"])

        located = client.get(
            "/api/v1/properties",
            params={"location": "gulberg"},
            headers=org_context.headers,
        )
        assert located.json()["total"] == 1
        assert located.json()["items"][0]["location"] == "Gulberg III, Lahore"

    def test_cross_tenant_property_is_404(
        self, client: TestClient, org_context: OrgContext, other_org_context: OrgContext
    ) -> None:
        victim = other_org_context.properties[0].id
        response = client.get(f"/api/v1/properties/{victim}", headers=org_context.headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestAgents:
    def test_me(self, client: TestClient, org_context: OrgContext) -> None:
        response = client.get("/api/v1/agents/me", headers=org_context.headers)

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["organization_id"] == str(org_context.org.id)
        assert body["role"] == "OWNER"
        assert body["name"] == "Owner One"

    def test_list_only_own_org(
        self, client: TestClient, org_context: OrgContext, other_org_context: OrgContext
    ) -> None:
        response = client.get("/api/v1/agents", headers=org_context.headers)

        assert response.status_code == status.HTTP_200_OK
        emails = {a["email"] for a in response.json()}
        assert emails == {org_context.owner.email, org_context.teammate.email}


class TestAnalytics:
    def test_overview_matches_seed(self, client: TestClient, org_context: OrgContext) -> None:
        response = client.get("/api/v1/analytics/overview", headers=org_context.headers)

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["total_leads"] == 4
        assert body["by_status"] == {
            "NEW": 1,
            "CONTACTED": 1,
            "QUALIFIED": 1,
            "CONVERTED": 1,
            "LOST": 0,
        }
        assert body["hot_leads"] == 2  # 85, 90
        assert body["warm_leads"] == 1  # 60
        assert body["cold_leads"] == 1  # unscored
        assert body["conversion_rate"] == 0.25
        assert abs(body["avg_qualification_score"] - (60 + 85 + 90) / 3) < 0.01
        assert body["new_leads_7d"] == 4
        assert body["total_properties"] == 2

    def test_overview_is_tenant_scoped(
        self, client: TestClient, org_context: OrgContext, other_org_context: OrgContext
    ) -> None:
        mine = client.get("/api/v1/analytics/overview", headers=org_context.headers).json()
        theirs = client.get("/api/v1/analytics/overview", headers=other_org_context.headers).json()

        assert mine["total_leads"] == theirs["total_leads"] == 4  # identical seeds
        assert mine["total_properties"] == theirs["total_properties"] == 2
        # but the organizations are distinct tenants
        assert org_context.org.id != other_org_context.org.id
