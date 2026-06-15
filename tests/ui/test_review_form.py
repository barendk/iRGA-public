"""Playwright UI tests for the reviews form display (/reviews).

Tests that the page loads, the sidebar controls are present,
and that selecting a team + monthly cycle renders the full
PPP form with per-goal confidence radio buttons.
"""

import pytest
from playwright.sync_api import Page, expect

# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture()
def reviews_page(ui_page: Page, base_url: str) -> Page:
    """Navigate to /reviews (no params — empty state)."""
    ui_page.goto(f"{base_url}/reviews")
    return ui_page


@pytest.fixture()
def reviews_form_page(ui_page: Page, base_url: str) -> Page:
    """Open /reviews, select Team Alpha + Januari 2026, click Tonen.

    Returns the page once the full monthly review form is visible.
    Team Alpha has 2 goals for 2026Q1 in the sample data.
    """
    ui_page.goto(f"{base_url}/reviews")

    # Select team
    ui_page.locator("[data-testid='entity-select']").select_option(label="Team Alpha")

    # Select a monthly cycle — Januari 2026 maps to 2026Q1 where Team Alpha's goals live
    ui_page.locator("[data-testid='cycle-select']").select_option(label="Januari 2026")

    # Submit the sidebar GET form
    ui_page.locator("button", has_text="Tonen").click()
    ui_page.wait_for_load_state("networkidle")

    return ui_page


# ── Page renders ───────────────────────────────────────────────────────────────


class TestReviewsPageRenders:
    """Basic page load checks."""

    def test_page_title(self, reviews_page: Page) -> None:
        expect(reviews_page).to_have_title("Reviews - My Organisation")

    def test_nav_active_link(self, reviews_page: Page) -> None:
        """'Reviews' nav link should be highlighted as the active page."""
        active_link = reviews_page.locator("nav a.text-primary.font-semibold", has_text="Reviews")
        expect(active_link).to_be_visible()

    def test_empty_state_shown_by_default(self, reviews_page: Page) -> None:
        """Without a selection, the empty-state prompt should be visible."""
        expect(reviews_page.locator("[data-testid='empty-state']")).to_be_visible()


# ── Sidebar controls ───────────────────────────────────────────────────────────


class TestReviewsSidebar:
    """Test that the sidebar filter controls are present and populated."""

    def test_team_select_present(self, reviews_page: Page) -> None:
        expect(reviews_page.locator("[data-testid='entity-select']")).to_be_visible()

    def test_team_select_populated(self, reviews_page: Page) -> None:
        """Team Alpha, Beta, Gamma should be in the dropdown from the seeded data."""
        select = reviews_page.locator("[data-testid='entity-select']")
        for team_name in ["Team Alpha", "Team Beta", "Team Gamma"]:
            expect(select.locator(f"option:text('{team_name}')")).to_have_count(1)

    def test_type_select_present(self, reviews_page: Page) -> None:
        expect(reviews_page.locator("#review-type-select")).to_be_visible()

    def test_type_select_has_monthly_option(self, reviews_page: Page) -> None:
        opt = reviews_page.locator("#review-type-select option[value='monthly']")
        expect(opt).to_have_count(1)

    def test_type_select_has_quarterly_option(self, reviews_page: Page) -> None:
        opt = reviews_page.locator("#review-type-select option[value='quarterly']")
        expect(opt).to_have_count(1)

    def test_cycle_select_present(self, reviews_page: Page) -> None:
        expect(reviews_page.locator("[data-testid='cycle-select']")).to_be_visible()

    def test_cycle_select_has_monthly_cycles(self, reviews_page: Page) -> None:
        """Auto-seeded monthly cycles should appear (e.g. Januari 2026)."""
        select = reviews_page.locator("[data-testid='cycle-select']")
        expect(select.locator("option:text('Januari 2026')")).to_have_count(1)

    def test_cycle_select_has_quarterly_cycles(self, reviews_page: Page) -> None:
        """Auto-seeded quarterly cycles should appear (e.g. 2026 Q1)."""
        select = reviews_page.locator("[data-testid='cycle-select']")
        expect(select.locator("option:text('2026 Q1')")).to_have_count(1)

    def test_tonen_button_present(self, reviews_page: Page) -> None:
        expect(reviews_page.locator("button", has_text="Tonen")).to_be_visible()


# ── Monthly review form ────────────────────────────────────────────────────────


class TestMonthlyReviewFormDisplay:
    """Test that the full form appears after selecting team + monthly cycle."""

    def test_form_heading_includes_team_name(self, reviews_form_page: Page) -> None:
        heading = reviews_form_page.locator("h2", has_text="Review: Team Alpha")
        expect(heading).to_be_visible()

    def test_monthly_badge_visible(self, reviews_form_page: Page) -> None:
        # Use a span/div locator to avoid matching the hidden <option> element
        badge = reviews_form_page.locator("span, div").filter(has_text="Maandelijkse Check-in")
        expect(badge.first).to_be_visible()

    def test_progress_textarea_visible(self, reviews_form_page: Page) -> None:
        expect(reviews_form_page.locator("[data-testid='progress-textarea']")).to_be_visible()

    def test_problems_textarea_visible(self, reviews_form_page: Page) -> None:
        expect(reviews_form_page.locator("[data-testid='problems-textarea']")).to_be_visible()

    def test_plans_textarea_visible(self, reviews_form_page: Page) -> None:
        expect(reviews_form_page.locator("[data-testid='plans-textarea']")).to_be_visible()

    def test_support_checkbox_visible(self, reviews_form_page: Page) -> None:
        expect(reviews_form_page.locator("[data-testid='support-checkbox']")).to_be_visible()

    def test_support_checkbox_clickable(self, reviews_form_page: Page) -> None:
        cb = reviews_form_page.locator("[data-testid='support-checkbox']")
        expect(cb).not_to_be_checked()
        cb.click()
        expect(cb).to_be_checked()

    def test_submit_button_visible(self, reviews_form_page: Page) -> None:
        expect(reviews_form_page.locator("[data-testid='submit-btn']")).to_be_visible()

    def test_confidence_radios_present_for_team_alpha_goals(self, reviews_form_page: Page) -> None:
        """Team Alpha has 3 goals for 2026Q1 — each should get 10 radio buttons."""
        # Each goal renders a confidence_radios macro → 10 radio inputs per goal,
        # named confidence_{goal_id}. We look for radio inputs starting with "confidence_".
        radios = reviews_form_page.locator("input[type='radio'][name^='confidence_']")
        # 3 goals × 10 buttons = 30 radio inputs
        expect(radios).to_have_count(30)

    def test_goal_texts_visible(self, reviews_form_page: Page) -> None:
        """All three Team Alpha goal titles should appear in the form."""
        for text in [
            "Refactor authentication module",
            "Migrate legacy database schemas",
            "Execute user review and implement UI changes",
        ]:
            expect(reviews_form_page.locator(f"text={text}")).to_be_visible()
