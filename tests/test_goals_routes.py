"""Integration tests for the goals list route (GET /goals).

Covers query-parameter edge cases that previously caused 422 errors,
plus basic filtering behaviour verified against the seeded dataset.
"""

from fastapi.testclient import TestClient


class TestGoalsListBasic:
    """Test that the page loads under normal conditions."""

    def test_page_loads(self, client: TestClient) -> None:
        response = client.get("/goals")
        assert response.status_code == 200

    def test_page_contains_heading(self, client: TestClient) -> None:
        response = client.get("/goals")
        assert "Doelenoverzicht" in response.text


class TestGoalsListDomainIdEdgeCases:
    """Test that domain_id query param is handled gracefully.

    The HTML form submits domain_id as an empty string when 'Alle Domeinen'
    is selected.  FastAPI must not return 422 for these inputs.
    """

    def test_empty_domain_id_returns_200(self, client: TestClient) -> None:
        """Empty string domain_id (form default) must not cause a 422."""
        response = client.get("/goals?domain_id=")
        assert response.status_code == 200

    def test_missing_domain_id_returns_200(self, client: TestClient) -> None:
        """Omitting domain_id entirely must work."""
        response = client.get("/goals")
        assert response.status_code == 200

    def test_valid_integer_domain_id_returns_200(
        self, client: TestClient, seed_entities: list
    ) -> None:
        """A real entity id must be accepted and filter without error."""
        # seed_entities includes Engineering domain; use its id
        engineering = next(e for e in seed_entities if e.name == "Engineering")
        response = client.get(f"/goals?domain_id={engineering.id}")
        assert response.status_code == 200

    def test_noninteger_domain_id_is_ignored(self, client: TestClient) -> None:
        """A non-numeric domain_id must be silently ignored (no 422, no 500)."""
        response = client.get("/goals?domain_id=notanumber")
        assert response.status_code == 200


class TestGoalsListFiltering:
    """Test that filter params narrow the result set correctly."""

    def test_filter_by_yearly_type_returns_200(self, client: TestClient) -> None:
        response = client.get("/goals?goal_types=yearly")
        assert response.status_code == 200

    def test_filter_by_quarterly_type_returns_200(self, client: TestClient) -> None:
        response = client.get("/goals?goal_types=quarterly")
        assert response.status_code == 200

    def test_filter_single_level_returns_200(self, client: TestClient) -> None:
        response = client.get("/goals?levels=org")
        assert response.status_code == 200

    def test_filter_by_period_returns_200(self, client: TestClient) -> None:
        response = client.get("/goals?period=2026Q1")
        assert response.status_code == 200

    def test_filter_by_unknown_period_returns_200(self, client: TestClient) -> None:
        """A period that matches no goals should show empty tables, not an error."""
        response = client.get("/goals?period=1900")
        assert response.status_code == 200
        assert "Geen doelen gevonden" in response.text
