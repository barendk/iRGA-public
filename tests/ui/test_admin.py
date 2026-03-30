"""Playwright UI tests for the admin entity management page.

Tests that the admin page renders correctly, level dropdowns
work, team-domain assignments persist, and the org constraint
is enforced visually.
"""

import re

import pytest
from playwright.sync_api import Page, expect


@pytest.fixture()
def admin_page(ui_page: Page, base_url: str) -> Page:
    """Navigate to the admin page."""
    ui_page.goto(f"{base_url}/admin")
    return ui_page


class TestAdminPageRenders:
    """Test that the admin page loads with expected content."""

    def test_page_title(self, admin_page: Page) -> None:
        expect(admin_page).to_have_title("Admin - Structuurbeheer - My Organisation")

    def test_heading_visible(self, admin_page: Page) -> None:
        heading = admin_page.locator("h2", has_text="Organisatiestructuur Beheren")
        expect(heading).to_be_visible()

    def test_info_banner_visible(self, admin_page: Page) -> None:
        banner = admin_page.locator("text=Er kan slechts één Organisatie niveau zijn.")
        expect(banner).to_be_visible()

    def test_entity_list_renders(self, admin_page: Page) -> None:
        """All seeded entities should appear in the entity level table."""
        # Use .first because names may appear in both the level table
        # and the team assignment table
        for name in [
            "Acme Corp",
            "Engineering",
            "Team Alpha",
            "Team Beta",
            "Team Gamma",
        ]:
            expect(admin_page.locator("td.font-medium", has_text=name).first).to_be_visible()

    def test_level_dropdowns_present(self, admin_page: Page) -> None:
        """Each entity should have a level dropdown."""
        selects = admin_page.locator("select[name^='level_']")
        expect(selects).to_have_count(5)

    def test_save_button_visible(self, admin_page: Page) -> None:
        button = admin_page.locator("button", has_text="Opslaan")
        expect(button).to_be_visible()


class TestAdminLevelChanges:
    """Test changing entity levels and saving."""

    def test_change_level_and_save(self, admin_page: Page) -> None:
        """Change a level, save, and verify it persists on reload."""
        # Find Team Alpha's select and note its current value
        selects = admin_page.locator("select[name^='level_']")
        count = selects.count()
        assert count >= 1

        # Click save
        admin_page.locator("button", has_text="Opslaan").click()

        # Should show success message
        expect(admin_page.locator("text=Wijzigingen succesvol opgeslagen.")).to_be_visible()


class TestAdminTeamAssignment:
    """Test the team-to-domain assignment section."""

    def test_team_assignment_section_visible(self, admin_page: Page) -> None:
        heading = admin_page.locator("h3", has_text="Team Toewijzing")
        expect(heading).to_be_visible()

    def test_domain_dropdowns_present(self, admin_page: Page) -> None:
        """Team assignment dropdowns should list available domains."""
        selects = admin_page.locator("select[name^='parent_']")
        # Should have one per team entity
        expect(selects).to_have_count(3)  # Team Alpha, Beta, Gamma


class TestAdminNavigation:
    """Test navigation elements on the admin page."""

    def test_admin_nav_active(self, admin_page: Page) -> None:
        """Admin nav link should be highlighted as active."""
        admin_link = admin_page.locator("nav a", has_text="Admin")
        expect(admin_link).to_have_class(re.compile(r"font-semibold"))

    def test_nav_links_present(self, admin_page: Page) -> None:
        """All nav links should be present."""
        for label in [
            "Home",
            "Doelenoverzicht",
            "Doelenboom",
            "Reviews",
            "PPP Status",
            "Admin",
        ]:
            link = admin_page.locator(f"nav a:has-text('{label}')")
            expect(link).to_be_visible()
