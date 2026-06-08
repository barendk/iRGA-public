"""Security tests for CSRF protection and input length limits.

Covers:
- POST /admin and POST /reviews are rejected (403) without a valid CSRF token.
- POST /reviews rejects PPP text fields that exceed the 5 000-character limit.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.cycle import ReviewCycle
from app.models.entity import StructuralEntity
from app.models.goal import Goal
from app.routes.reviews import MAX_PPP_LEN

# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture()
def team(db: Session) -> StructuralEntity:
    entity = StructuralEntity(name="Test Team", level="team")
    db.add(entity)
    db.flush()
    return entity


@pytest.fixture()
def monthly_cycle(db: Session) -> ReviewCycle:
    cycle = ReviewCycle(
        name="Januari 2026",
        cycle_type="monthly",
        period="2026-01",
        status="open",
    )
    db.add(cycle)
    db.flush()
    return cycle


@pytest.fixture()
def goal(db: Session, team: StructuralEntity) -> Goal:
    g = Goal(
        github_issue_id=1,
        github_url="https://github.com/org/repo/issues/1",
        title="Test Team - 2026Q1 - Test doel",
        parsed_text="Test doel",
        period="2026Q1",
        period_type="quarterly",
        entity_id=team.id,
    )
    db.add(g)
    db.flush()
    return g


def _get_csrf(client: TestClient, url: str = "/admin") -> str:
    """GET a page to receive the CSRF cookie, then return its value."""
    client.get(url)
    return client.cookies["csrftoken"]


def _valid_review_payload(
    team: StructuralEntity,
    cycle: ReviewCycle,
    csrf: str,
    goal: Goal,
    *,
    progress: str = "Voortgang tekst",
    problems: str = "Problemen tekst",
    plans: str = "Plannen tekst",
) -> dict:
    return {
        "csrftoken": csrf,
        "entity_id": str(team.id),
        "cycle_id": str(cycle.id),
        "progress": progress,
        "problems": problems,
        "plans": plans,
        f"confidence_{goal.id}": "7",
    }


# ── CSRF — /admin ───────────────────────────────────────────────────────────


class TestCsrfAdmin:
    def test_post_without_csrf_token_returns_403(
        self, client: TestClient, seed_entities: list
    ) -> None:
        """POST /admin without csrftoken form field must be rejected."""
        client.get("/admin")  # sets the cookie but we intentionally omit the field
        entities = seed_entities
        response = client.post(
            "/admin",
            data={f"level_{entities[0].id}": "org"},  # no csrftoken!
        )
        assert response.status_code == 403

    def test_post_with_wrong_csrf_token_returns_403(
        self, client: TestClient, seed_entities: list
    ) -> None:
        """POST /admin with an incorrect csrftoken value must be rejected."""
        client.get("/admin")
        entities = seed_entities
        response = client.post(
            "/admin",
            data={
                "csrftoken": "totally-wrong-token",
                f"level_{entities[0].id}": "org",
            },
        )
        assert response.status_code == 403

    def test_post_with_valid_csrf_token_succeeds(
        self, client: TestClient, seed_entities: list
    ) -> None:
        """POST /admin with the correct csrftoken must be accepted (200)."""
        csrf = _get_csrf(client)
        entities = seed_entities
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


# ── CSRF — /reviews ─────────────────────────────────────────────────────────


class TestCsrfReviews:
    def test_post_without_csrf_token_returns_403(
        self,
        client: TestClient,
        team: StructuralEntity,
        monthly_cycle: ReviewCycle,
        goal: Goal,
    ) -> None:
        """POST /reviews without csrftoken form field must be rejected."""
        client.get("/reviews")  # sets the cookie
        response = client.post(
            "/reviews",
            data={
                # csrftoken intentionally omitted
                "entity_id": str(team.id),
                "cycle_id": str(monthly_cycle.id),
                "progress": "ok",
                "problems": "ok",
                "plans": "ok",
                f"confidence_{goal.id}": "7",
            },
        )
        assert response.status_code == 403

    def test_post_with_valid_csrf_token_succeeds(
        self,
        client: TestClient,
        team: StructuralEntity,
        monthly_cycle: ReviewCycle,
        goal: Goal,
    ) -> None:
        """POST /reviews with a valid csrftoken must be accepted."""
        csrf = _get_csrf(client, "/reviews")
        response = client.post(
            "/reviews",
            data=_valid_review_payload(team, monthly_cycle, csrf, goal),
        )
        # Successful submit redirects to confirmation page
        assert response.status_code in (200, 303)


# ── Input length limits ──────────────────────────────────────────────────────


class TestInputLengthLimits:
    """Server-side max-length validation on the PPP text fields."""

    def _overlong(self) -> str:
        return "x" * (MAX_PPP_LEN + 1)

    def test_overlong_progress_returns_error(
        self,
        client: TestClient,
        team: StructuralEntity,
        monthly_cycle: ReviewCycle,
        goal: Goal,
    ) -> None:
        csrf = _get_csrf(client, "/reviews")
        response = client.post(
            "/reviews",
            data=_valid_review_payload(team, monthly_cycle, csrf, goal, progress=self._overlong()),
        )
        assert response.status_code == 200
        assert "5" in response.text  # limit mentioned in error message
        assert "Voortgang" in response.text

    def test_overlong_problems_returns_error(
        self,
        client: TestClient,
        team: StructuralEntity,
        monthly_cycle: ReviewCycle,
        goal: Goal,
    ) -> None:
        csrf = _get_csrf(client, "/reviews")
        response = client.post(
            "/reviews",
            data=_valid_review_payload(team, monthly_cycle, csrf, goal, problems=self._overlong()),
        )
        assert response.status_code == 200
        assert "Problemen" in response.text

    def test_overlong_plans_returns_error(
        self,
        client: TestClient,
        team: StructuralEntity,
        monthly_cycle: ReviewCycle,
        goal: Goal,
    ) -> None:
        csrf = _get_csrf(client, "/reviews")
        response = client.post(
            "/reviews",
            data=_valid_review_payload(team, monthly_cycle, csrf, goal, plans=self._overlong()),
        )
        assert response.status_code == 200
        assert "Plannen" in response.text

    def test_exactly_at_limit_is_accepted(
        self,
        client: TestClient,
        team: StructuralEntity,
        monthly_cycle: ReviewCycle,
        goal: Goal,
    ) -> None:
        csrf = _get_csrf(client, "/reviews")
        at_limit = "x" * MAX_PPP_LEN
        response = client.post(
            "/reviews",
            data=_valid_review_payload(
                team,
                monthly_cycle,
                csrf,
                goal,
                progress=at_limit,
                problems=at_limit,
                plans=at_limit,
            ),
        )
        # Should redirect to confirmation, not show an error
        assert response.status_code in (200, 303)
