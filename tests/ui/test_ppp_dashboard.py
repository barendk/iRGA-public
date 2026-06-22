"""Playwright UI tests for the PPP Status dashboard (/status).

Session-scoped fixture seeds a MonthlyReview for Team Alpha (Januari 2026)
with support_request=True directly via SQLAlchemy — same approach as conftest.py
_seed_test_data, which avoids cross-module browser-context ordering issues.

Test structure:
  TestDashboardRenders   — title, heading, nav "PPP Status" active
  TestFilterSidebar      — cycle select, domain select, Toepassen button
  TestProblemsSection    — all teams shown, escalation badge, red border on flagged card
  TestProgressSection    — progress cards visible
  TestPlansSection       — plans cards visible
  TestConfidenceSection  — distribution bars, per-goal table rows
"""

import pytest
from playwright.sync_api import Page, expect
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import DATABASE_URL

# ── Session fixture: seed review data once ─────────────────────────────────────


@pytest.fixture(scope="session")
def _submitted_review(_live_server: None) -> None:  # noqa: PT004
    """Seed a MonthlyReview + GoalConfidence records for Team Alpha, Januari 2026.

    Runs once per test session after the live server (and seed data) are up.
    Uses support_request=True so the escalation badge and red card border are
    visible on the dashboard.

    The save_review call is an upsert, so this is safe to run multiple times.
    """
    from app.models.cycle import ReviewCycle
    from app.models.entity import StructuralEntity
    from app.services.review_service import (
        get_goals_for_cycle,
        get_or_create_open_cycles,
        save_review,
    )

    engine = create_engine(DATABASE_URL, echo=False)
    session_factory = sessionmaker(bind=engine)
    db = session_factory()

    try:
        # Auto-seed cycles so "2026-01" exists.
        get_or_create_open_cycles(db)

        # Use Team Beta + Januari 2026 — isolated from existing tests:
        #   - Team Alpha + Januari 2026 is used by TestReviewSubmitSuccess
        #   - Team Beta + Februari 2026 is used by TestReviewPrefill
        #   - Team Gamma + Januari 2026 is used by TestReviewValidation
        # Team Beta + Januari 2026 is untouched by all existing tests.
        team = db.query(StructuralEntity).filter_by(name="Team Beta").first()
        cycle = db.query(ReviewCycle).filter_by(cycle_type="monthly", period="2026-01").first()

        if team is None or cycle is None:
            return  # Seed data not present — skip gracefully.

        goals = get_goals_for_cycle(db, team.id, cycle)
        confidences = {goal.id: 8 for goal in goals}

        save_review(
            db,
            entity_id=team.id,
            cycle_id=cycle.id,
            progress="Beta maakte grote stappen.",
            problems="Wachten op goedkeuring budget.",
            plans="Afronden migratie Q1.",
            support_request=True,
            confidences=confidences,
        )
    finally:
        db.close()
        engine.dispose()


# ── Page fixture: navigate to /status for Januari 2026 ─────────────────────────


@pytest.fixture()
def status_page(ui_page: Page, base_url: str, _submitted_review: None) -> Page:
    """Navigate to /status, select Januari 2026, click Toepassen.

    Returns the page once the dashboard is showing the Januari 2026 data.
    """
    ui_page.goto(f"{base_url}/status")
    ui_page.wait_for_load_state("networkidle")

    # Explicitly select Januari 2026 — the default may be a later month with
    # no data if today is past January 2026.
    ui_page.locator("[data-testid='cycle-select']").select_option(label="Januari 2026")
    ui_page.locator("button", has_text="Toepassen").click()
    ui_page.wait_for_load_state("networkidle")

    return ui_page


# ── TestDashboardRenders ───────────────────────────────────────────────────────


class TestDashboardRenders:
    """Basic page load and heading checks."""

    def test_page_title(self, status_page: Page) -> None:
        expect(status_page).to_have_title("PPP Status - My Organisation")

    def test_heading_visible(self, status_page: Page) -> None:
        expect(status_page.locator("h2", has_text="PPP Status Dashboard")).to_be_visible()

    def test_nav_ppp_status_active(self, status_page: Page) -> None:
        """The 'PPP Status' nav item should have the active border-primary class."""
        active_link = status_page.locator("nav a.border-primary", has_text="PPP Status")
        expect(active_link).to_be_visible()

    def test_selected_cycle_name_shown(self, status_page: Page) -> None:
        """The selected cycle name (Januari 2026) should appear below the heading."""
        # Target the subtitle <p> specifically to avoid matching the <option> element.
        expect(status_page.locator("p.text-gray-500", has_text="Januari 2026")).to_be_visible()


# ── TestFilterSidebar ──────────────────────────────────────────────────────────


class TestFilterSidebar:
    """Filter sidebar controls are present and populated."""

    def test_cycle_select_present(self, status_page: Page) -> None:
        expect(status_page.locator("[data-testid='cycle-select']")).to_be_visible()

    def test_cycle_select_has_options(self, status_page: Page) -> None:
        """Cycle dropdown should have at least one option (auto-seeded cycles)."""
        options = status_page.locator("[data-testid='cycle-select'] option")
        expect(options).to_have_count(
            status_page.locator("[data-testid='cycle-select'] option").count()
        )
        assert status_page.locator("[data-testid='cycle-select'] option").count() >= 1

    def test_domain_select_present(self, status_page: Page) -> None:
        expect(status_page.locator("[data-testid='domain-select']")).to_be_visible()

    def test_toepassen_button_present(self, status_page: Page) -> None:
        expect(status_page.locator("button", has_text="Toepassen")).to_be_visible()


# ── TestProblemsSection ────────────────────────────────────────────────────────


class TestProblemsSection:
    """Problems & Blokkades section shows all teams; flagged cards are highlighted."""

    def test_problems_heading_visible(self, status_page: Page) -> None:
        expect(status_page.locator("h3", has_text="Problemen & Blokkades")).to_be_visible()

    def test_team_beta_card_visible(self, status_page: Page) -> None:
        """Team Beta's problems card should show the team name."""
        problem_cards = status_page.locator("[data-testid='problem-card']")
        team_names = problem_cards.locator("span.uppercase", has_text="Team Beta")
        expect(team_names.first).to_be_visible()

    def test_escalation_badge_visible(self, status_page: Page) -> None:
        """'Geëscaleerd' badge should appear when support_request=True."""
        expect(status_page.locator("text=Geëscaleerd").first).to_be_visible()

    def test_escalated_count_badge_visible(self, status_page: Page) -> None:
        """The section header badge shows how many teams escalated (≥ 1)."""
        # The badge looks like "1 Geëscaleerd" (uppercase, in the section heading row).
        header_badge = status_page.locator("[data-testid='problems-section'] span.bg-red-600")
        expect(header_badge).to_be_visible()

    def test_flagged_card_has_red_border(self, status_page: Page) -> None:
        """A card from a team with support_request=True must have the red left-border class."""
        red_border_cards = status_page.locator("[data-testid='problem-card'].border-l-red-500")
        expect(red_border_cards.first).to_be_visible()

    def test_problems_text_shown(self, status_page: Page) -> None:
        expect(status_page.locator("p", has_text="Wachten op goedkeuring budget.")).to_be_visible()


# ── TestProgressSection ────────────────────────────────────────────────────────


class TestProgressSection:
    """Voortgang & Winst section shows progress cards."""

    def test_progress_heading_visible(self, status_page: Page) -> None:
        expect(status_page.locator("h3", has_text="Voortgang & Winst")).to_be_visible()

    def test_team_beta_progress_card_visible(self, status_page: Page) -> None:
        progress_cards = status_page.locator("[data-testid='progress-card']")
        expect(progress_cards.first).to_be_visible()

    def test_progress_text_shown(self, status_page: Page) -> None:
        expect(status_page.locator("p", has_text="Beta maakte grote stappen.")).to_be_visible()


# ── TestPlansSection ───────────────────────────────────────────────────────────


class TestPlansSection:
    """Plannen section shows plans cards."""

    def test_plans_heading_visible(self, status_page: Page) -> None:
        expect(status_page.locator("h3", has_text="Plannen")).to_be_visible()

    def test_team_beta_plans_card_visible(self, status_page: Page) -> None:
        plans_cards = status_page.locator("[data-testid='plans-card']")
        expect(plans_cards.first).to_be_visible()

    def test_plans_text_shown(self, status_page: Page) -> None:
        expect(status_page.locator("p", has_text="Afronden migratie Q1.")).to_be_visible()


# ── TestConfidenceSection ──────────────────────────────────────────────────────


class TestConfidenceSection:
    """Vertrouwen Dashboard shows distribution bars and per-goal table."""

    def test_confidence_section_visible(self, status_page: Page) -> None:
        expect(status_page.locator("h3", has_text="Vertrouwen Dashboard")).to_be_visible()

    def test_distribution_bars_present(self, status_page: Page) -> None:
        """The confidence-bars container should be present (Team Alpha has scores)."""
        expect(status_page.locator("[data-testid='confidence-bars']")).to_be_visible()

    def test_green_bar_present(self, status_page: Page) -> None:
        """Score 8 is green (≥7), so the green bar should be visible."""
        expect(status_page.locator("[data-testid='bar-green']")).to_be_visible()

    def test_confidence_table_present(self, status_page: Page) -> None:
        expect(status_page.locator("[data-testid='confidence-table']")).to_be_visible()

    def test_at_least_one_confidence_row(self, status_page: Page) -> None:
        """Team Alpha has goals for 2026Q1, so at least one row should be present."""
        rows = status_page.locator("[data-testid='confidence-row']")
        assert rows.count() >= 1

    def test_avg_confidence_stats_present(self, status_page: Page) -> None:
        """Summary stats block (Gemiddeld / vs vorige maand / Teams ingediend) is visible."""
        expect(status_page.locator("[data-testid='confidence-stats']")).to_be_visible()

    def test_gemiddeld_label_visible(self, status_page: Page) -> None:
        expect(status_page.locator("text=Gemiddeld")).to_be_visible()

    def test_teams_ingediend_label_visible(self, status_page: Page) -> None:
        expect(status_page.locator("text=Teams ingediend")).to_be_visible()
