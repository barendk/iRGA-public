"""Integration tests for the admin route.

Tests GET/POST /admin with entity level changes,
team-domain assignments, and validation constraints.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.entity import StructuralEntity


class TestAdminGet:
    """Test GET /admin displays entities correctly."""

    def test_admin_page_loads(self, client: TestClient) -> None:
        response = client.get("/admin")
        assert response.status_code == 200
        assert "Organisatiestructuur Beheren" in response.text

    def test_shows_entities_with_dropdowns(self, client: TestClient, seed_entities: list) -> None:
        response = client.get("/admin")
        assert response.status_code == 200
        assert "Acme Corp" in response.text
        assert "Engineering" in response.text
        assert "Team Alpha" in response.text
        # Check level dropdowns are present
        assert "level_" in response.text

    def test_shows_team_assignment_section(self, client: TestClient, seed_entities: list) -> None:
        response = client.get("/admin")
        assert "Team Toewijzing" in response.text
        assert "Bovenliggend Domein" in response.text

    def test_empty_state(self, client: TestClient) -> None:
        """When no entities exist, show empty message."""
        response = client.get("/admin")
        assert "Geen entiteiten gevonden" in response.text


def _csrf_token(client: TestClient) -> str:
    """Fetch /admin to obtain a CSRF cookie, then return its value."""
    client.get("/admin")
    return client.cookies["csrftoken"]


class TestAdminPost:
    """Test POST /admin saves changes correctly."""

    def test_save_level_changes(self, client: TestClient, db: Session, seed_entities: list) -> None:
        entities = seed_entities
        csrf = _csrf_token(client)
        response = client.post(
            "/admin",
            data={
                "csrftoken": csrf,
                f"level_{entities[0].id}": "org",
                f"level_{entities[1].id}": "domain",
                f"level_{entities[2].id}": "team",
                f"level_{entities[3].id}": "team",
                f"level_{entities[4].id}": "team",
            },
        )
        assert response.status_code == 200
        assert "succesvol" in response.text

    def test_single_org_constraint(self, client: TestClient, seed_entities: list) -> None:
        """Setting two entities to 'org' should show an error."""
        entities = seed_entities
        csrf = _csrf_token(client)
        response = client.post(
            "/admin",
            data={
                "csrftoken": csrf,
                f"level_{entities[0].id}": "org",
                f"level_{entities[1].id}": "org",  # Two orgs!
                f"level_{entities[2].id}": "team",
                f"level_{entities[3].id}": "team",
                f"level_{entities[4].id}": "team",
            },
        )
        assert response.status_code == 200
        assert "slechts één" in response.text

    def test_team_domain_assignment(
        self, client: TestClient, db: Session, seed_entities: list
    ) -> None:
        entities = seed_entities
        domain_id = entities[1].id  # Engineering
        team_id = entities[2].id  # Team Alpha
        csrf = _csrf_token(client)

        response = client.post(
            "/admin",
            data={
                "csrftoken": csrf,
                f"level_{entities[0].id}": "org",
                f"level_{entities[1].id}": "domain",
                f"level_{entities[2].id}": "team",
                f"level_{entities[3].id}": "team",
                f"level_{entities[4].id}": "team",
                f"parent_{team_id}": str(domain_id),
            },
        )
        assert response.status_code == 200
        assert "succesvol" in response.text

        # Verify the assignment persisted
        db.expire_all()
        team = db.get(StructuralEntity, team_id)
        assert team is not None
        assert team.parent_id == domain_id
