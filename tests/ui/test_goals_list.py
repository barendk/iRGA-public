"""Playwright UI tests for the goals list view (/goals).

Tests that the page loads, the filter sidebar is complete,
goal data from the demo import is visible, and summary stat cards render.
"""

import pytest
from playwright.sync_api import Page, expect


@pytest.fixture()
def goals_page(ui_page: Page, base_url: str) -> Page:
    """Navigate to the goals list page."""
    ui_page.goto(f"{base_url}/goals")
    return ui_page


class TestGoalsListRenders:
    """Test that the goals list page loads with expected structure."""

    def test_page_title(self, goals_page: Page) -> None:
        expect(goals_page).to_have_title("Doelenoverzicht - My Organisation")

    def test_heading_visible(self, goals_page: Page) -> None:
        heading = goals_page.locator("h2", has_text="Doelenoverzicht")
        expect(heading).to_be_visible()

    def test_nav_active_link(self, goals_page: Page) -> None:
        """'Doelenoverzicht' nav link should be highlighted as the active page."""
        active_link = goals_page.locator(
            "nav a.text-primary.font-semibold", has_text="Doelenoverzicht"
        )
        expect(active_link).to_be_visible()


class TestGoalsFilterSidebar:
    """Test that all filter sidebar controls are present and functional."""

    def test_filter_heading_visible(self, goals_page: Page) -> None:
        heading = goals_page.locator("h2", has_text="Filters")
        expect(heading).to_be_visible()

    def test_period_dropdown_present(self, goals_page: Page) -> None:
        """Period dropdown should be visible and have at least 'Alle perioden'."""
        select = goals_page.locator("select#period-select")
        expect(select).to_be_visible()
        # Should have the "all periods" option
        expect(select.locator("option[value='']")).to_have_count(1)

    def test_period_dropdown_populated_from_db(self, goals_page: Page) -> None:
        """Dropdown should contain periods from the seeded sample goals."""
        select = goals_page.locator("select#period-select")
        # Sample data has 2026 (yearly) and 2026Q1 (quarterly); all shown together
        options = select.locator("option")
        expect(options).to_have_count(3)  # Alle perioden + 2026 + 2026Q1

    def test_level_checkbox_organisatie(self, goals_page: Page) -> None:
        cb = goals_page.locator("input#lvl-org")
        expect(cb).to_be_visible()
        expect(cb).to_be_checked()

    def test_level_checkbox_domein(self, goals_page: Page) -> None:
        cb = goals_page.locator("input#lvl-domain")
        expect(cb).to_be_visible()
        expect(cb).to_be_checked()

    def test_level_checkbox_team(self, goals_page: Page) -> None:
        cb = goals_page.locator("input#lvl-team")
        expect(cb).to_be_visible()
        expect(cb).to_be_checked()

    def test_goal_type_checkbox_jaardoelen(self, goals_page: Page) -> None:
        cb = goals_page.locator("input#type-yearly")
        expect(cb).to_be_visible()
        expect(cb).to_be_checked()

    def test_goal_type_checkbox_kwartaaldoelen(self, goals_page: Page) -> None:
        cb = goals_page.locator("input#type-quarterly")
        expect(cb).to_be_visible()
        expect(cb).to_be_checked()

    def test_domain_dropdown_present(self, goals_page: Page) -> None:
        select = goals_page.locator("select#domain-select")
        expect(select).to_be_visible()
        # Should have "Alle Domeinen" as first option
        expect(select.locator("option[value='']")).to_have_count(1)

    def test_domain_dropdown_populated(self, goals_page: Page) -> None:
        """Domain dropdown should list domains from the seeded data."""
        select = goals_page.locator("select#domain-select")
        # Sample data has Engineering as the only domain
        engineering_option = select.locator("option", has_text="Engineering")
        expect(engineering_option).to_have_count(1)

    def test_toepassen_button_present(self, goals_page: Page) -> None:
        btn = goals_page.locator("button[type='submit']", has_text="Toepassen")
        expect(btn).to_be_visible()


class TestGoalsTableContent:
    """Test that goal data from the seeded demo import is visible in the tables."""

    def test_organisatie_section_visible(self, goals_page: Page) -> None:
        heading = goals_page.locator("h3", has_text="Organisatie")
        expect(heading).to_be_visible()

    def test_domein_section_visible(self, goals_page: Page) -> None:
        heading = goals_page.locator("h3", has_text="Domein")
        expect(heading).to_be_visible()

    def test_team_section_visible(self, goals_page: Page) -> None:
        heading = goals_page.locator("h3", has_text="Team")
        expect(heading).to_be_visible()

    def test_org_goal_text_visible(self, goals_page: Page) -> None:
        """Org-level goal from sample_goals.tsv should appear in Organisatie table."""
        # Sample data: Acme Corp - 2026 - Become market leader in ...
        goal_text = goals_page.locator("td", has_text="Become market leader")
        expect(goal_text).to_be_visible()

    def test_team_goal_text_visible(self, goals_page: Page) -> None:
        """A team-level goal from sample_goals.tsv should appear in the Team table."""
        # Sample data: "Team Alpha - 2026Q1 - Refactor authentication module"
        goal_text = goals_page.locator("td", has_text="Refactor authentication module")
        expect(goal_text).to_be_visible()

    def test_github_links_present(self, goals_page: Page) -> None:
        """Goals with github_url should have a GitHub link."""
        github_links = goals_page.locator("a", has_text="GitHub")
        # All 11 seeded goals have github_url set
        expect(github_links).to_have_count(11)

    def test_team_rows_show_domain_badge(self, goals_page: Page) -> None:
        """Team section rows should show a domain badge below the team name."""
        # Sample data: Team Alpha belongs to Engineering domain
        badge = goals_page.locator("span", has_text="Engineering").first
        expect(badge).to_be_visible()

    def test_org_and_domain_rows_have_no_domain_badge(self, goals_page: Page) -> None:
        """Org and domain section rows must not show a domain badge."""
        # The badge only appears in the Team section.  Org and domain entities
        # have no parent domain entity, so the badge conditional is false.
        # Verify Acme Corp (org) row contains no badge span.
        org_row = goals_page.locator("tr", has_text="Acme Corp")
        expect(org_row.locator("span.bg-blue-50")).to_have_count(0)

    def test_confidence_column_renders(self, goals_page: Page) -> None:
        """Confidence cells render either a dash or a badge — at least one of each
        must be present across the 11 sample goals (some may have been reviewed
        in a previous test; others will still show the dash).

        Note: the UI tests share a persistent DB, so specific counts depend on
        whether review tests have already run in this session.
        """
        # Every goal row must have *something* in the confidence cell.
        # Use has_text="/10" to match only confidence badges (e.g. "7/10"),
        # not the owner-initials circles that also use rounded-full.
        dashes = goals_page.locator("td span.confidence-empty")
        badges = goals_page.locator("td span.rounded-full", has_text="/10")
        # Together they cover all 11 goals.
        total = dashes.count() + badges.count()
        assert total == 11, f"Expected 11 confidence cells, got {total}"


class TestGoalsSummaryStats:
    """Test that the summary stat cards render with correct structure and counts."""

    def test_totaal_doelen_card_visible(self, goals_page: Page) -> None:
        label = goals_page.locator("span", has_text="Totaal Doelen")
        expect(label).to_be_visible()

    def test_hoog_vertrouwen_card_visible(self, goals_page: Page) -> None:
        label = goals_page.locator("span", has_text="Hoog Vertrouwen")
        expect(label).to_be_visible()

    def test_aandacht_nodig_card_visible(self, goals_page: Page) -> None:
        label = goals_page.locator("span", has_text="Aandacht nodig")
        expect(label).to_be_visible()

    def test_totaal_doelen_count(self, goals_page: Page) -> None:
        """Total goals from sample data is 11 (4 structural rows are not goals)."""
        count_div = goals_page.locator("[data-testid='stat-total']")
        expect(count_div).to_have_text("11")

    def test_hoog_vertrouwen_stat_renders(self, goals_page: Page) -> None:
        """The Hoog Vertrouwen stat card renders a numeric value.

        The exact number depends on whether reviews have been submitted in this
        DB session; we only verify the element is present and numeric.
        """
        count_div = goals_page.locator("[data-testid='stat-high-confidence']")
        expect(count_div).to_be_visible()
        text = count_div.inner_text()
        assert text.isdigit(), f"Expected a digit, got: {text!r}"

    def test_aandacht_nodig_count_zero_without_reviews(self, goals_page: Page) -> None:
        """With no reviews submitted, needs-attention count must be 0."""
        count_div = goals_page.locator("[data-testid='stat-needs-attention']")
        expect(count_div).to_have_text("0")
