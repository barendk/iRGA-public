"""Playwright UI tests for the goal tree view (/goals/tree).

The default filter is quarterly. With the seeded sample data the quarterly
tree contains:
  - 1 org quarterly goal  : "Become ISO certified"        (root, parent yearly filtered out)
  - 2 domain quarterly goals: "Reduce technical debt…"    (root, parent yearly filtered out)
                              "Implement automated deployment…"
  - 5 team quarterly goals  : children of the two domain goals above

No non-org goals have a null parent_goal_id, so the unaligned section is absent.
"""

import pytest
from playwright.sync_api import Page, expect


@pytest.fixture()
def tree_page(ui_page: Page, base_url: str) -> Page:
    """Navigate to the goal tree page (default: quarterly filter)."""
    ui_page.goto(f"{base_url}/goals/tree")
    return ui_page


@pytest.fixture()
def tree_page_yearly(ui_page: Page, base_url: str) -> Page:
    """Navigate to the goal tree page with the yearly filter active."""
    ui_page.goto(f"{base_url}/goals/tree?period_type_toggle=yearly")
    return ui_page


# ─────────────────────────────────────────────────────────────
# Page renders
# ─────────────────────────────────────────────────────────────


class TestGoalTreeRenders:
    """Basic page load checks."""

    def test_page_title(self, tree_page: Page) -> None:
        expect(tree_page).to_have_title("Doelenboom - My Organisation")

    def test_heading_visible(self, tree_page: Page) -> None:
        heading = tree_page.locator("h2", has_text="Doelenboom")
        expect(heading).to_be_visible()

    def test_nav_active_link(self, tree_page: Page) -> None:
        """'Doelenboom' nav link should be highlighted as the active page."""
        active_link = tree_page.locator("nav a.text-primary.font-semibold", has_text="Doelenboom")
        expect(active_link).to_be_visible()


# ─────────────────────────────────────────────────────────────
# Filter sidebar
# ─────────────────────────────────────────────────────────────


class TestGoalTreeFilterSidebar:
    """All filter controls should be present and correctly initialised."""

    def test_filter_heading_visible(self, tree_page: Page) -> None:
        heading = tree_page.locator("h2", has_text="Filters")
        expect(heading).to_be_visible()

    def test_kwartaal_toggle_visible(self, tree_page: Page) -> None:
        btn = tree_page.locator("button[data-toggle-period='quarterly']")
        expect(btn).to_be_visible()

    def test_jaarlijks_toggle_visible(self, tree_page: Page) -> None:
        btn = tree_page.locator("button[data-toggle-period='yearly']")
        expect(btn).to_be_visible()

    def test_kwartaal_is_default_active(self, tree_page: Page) -> None:
        """Kwartaal should be the active toggle on first load.

        Uses a CSS compound selector (.bg-primary) so the test works regardless
        of how Jinja2 formats the class attribute string.
        """
        active_btn = tree_page.locator("button[data-toggle-period='quarterly'].bg-primary")
        expect(active_btn).to_be_visible()

    def test_period_dropdown_present(self, tree_page: Page) -> None:
        select = tree_page.locator("select#period-select")
        expect(select).to_be_visible()
        # "Alle perioden" option must always be present.
        expect(select.locator("option[value='']")).to_have_count(1)

    def test_niveau_dropdown_present(self, tree_page: Page) -> None:
        select = tree_page.locator("select#level-select")
        expect(select).to_be_visible()
        expect(select.locator("option[value='']")).to_have_count(1)

    def test_domein_dropdown_present(self, tree_page: Page) -> None:
        select = tree_page.locator("select#domain-select")
        expect(select).to_be_visible()
        expect(select.locator("option[value='']")).to_have_count(1)

    def test_toepassen_button_present(self, tree_page: Page) -> None:
        btn = tree_page.locator("button[type='submit']", has_text="Toepassen")
        expect(btn).to_be_visible()


# ─────────────────────────────────────────────────────────────
# Hierarchy — at least one goal per level visible
# ─────────────────────────────────────────────────────────────


class TestGoalTreeHierarchy:
    """Goal data from the seeded TSV should be visible in the correct positions."""

    def test_org_goal_visible(self, tree_page: Page) -> None:
        """Quarterly org goal should appear in the default quarterly view."""
        goal = tree_page.locator("p", has_text="Become ISO certified")
        expect(goal).to_be_visible()

    def test_domain_goal_visible(self, tree_page: Page) -> None:
        """At least one domain-level quarterly goal should appear."""
        goal = tree_page.locator("p", has_text="Reduce technical debt by 30%")
        expect(goal).to_be_visible()

    def test_team_goal_visible(self, tree_page: Page) -> None:
        """At least one team-level quarterly goal should appear."""
        goal = tree_page.locator("p", has_text="Refactor authentication module")
        expect(goal).to_be_visible()

    def test_yearly_org_goal_visible_on_yearly_filter(self, tree_page_yearly: Page) -> None:
        """When switching to yearly filter the yearly org goal should appear."""
        goal = tree_page_yearly.locator("p", has_text="Become market leader")
        expect(goal).to_be_visible()

    def test_at_least_one_github_link(self, tree_page: Page) -> None:
        """At least one GitHub link should be present in the tree."""
        links = tree_page.locator("a", has_text="GitHub")
        expect(links.first).to_be_visible()

    def test_github_link_has_correct_href(self, tree_page: Page) -> None:
        """ISO certified org goal should link to issue #2."""
        link = tree_page.locator("a[href*='issues/2']")
        expect(link).to_be_visible()


# ─────────────────────────────────────────────────────────────
# Expand / collapse
# ─────────────────────────────────────────────────────────────


class TestGoalTreeExpandCollapse:
    """JS-driven expand/collapse behaviour."""

    def test_inklappen_button_visible_on_load(self, tree_page: Page) -> None:
        btn = tree_page.locator("#toggle-all-btn")
        expect(btn).to_be_visible()
        expect(btn.locator("#toggle-all-label")).to_have_text("Alles inklappen")

    def test_all_children_initially_visible(self, tree_page: Page) -> None:
        """Every children wrapper should be visible on first load (expanded)."""
        children_divs = tree_page.locator("[id^='children-']")
        count = children_divs.count()
        assert count > 0, "Expected at least one expandable node"
        for i in range(count):
            expect(children_divs.nth(i)).to_be_visible()

    def test_inklappen_hides_all_children(self, tree_page: Page) -> None:
        """Clicking 'Alles inklappen' should hide all children wrappers."""
        tree_page.locator("#toggle-all-btn").click()
        children_divs = tree_page.locator("[id^='children-']")
        count = children_divs.count()
        assert count > 0
        for i in range(count):
            expect(children_divs.nth(i)).to_be_hidden()

    def test_button_label_changes_to_uitklappen(self, tree_page: Page) -> None:
        """After collapsing, button label should read 'Alles uitklappen'."""
        tree_page.locator("#toggle-all-btn").click()
        expect(tree_page.locator("#toggle-all-label")).to_have_text("Alles uitklappen")

    def test_uitklappen_restores_children(self, tree_page: Page) -> None:
        """Clicking the button a second time should restore all children."""
        btn = tree_page.locator("#toggle-all-btn")
        btn.click()  # collapse
        btn.click()  # expand
        children_divs = tree_page.locator("[id^='children-']")
        count = children_divs.count()
        assert count > 0
        for i in range(count):
            expect(children_divs.nth(i)).to_be_visible()

    def test_per_node_toggle_hides_children(self, tree_page: Page) -> None:
        """Clicking a single node's expand button should hide only that node's children."""
        # Find the first per-node expand button.
        node_btn = tree_page.locator("[onclick^='toggleChildren']").first
        # Get the id of the corresponding children div.
        onclick_attr = node_btn.get_attribute("onclick")
        # onclick value: toggleChildren('children-42', this)
        children_id = onclick_attr.split("'")[1]  # e.g. "children-42"
        children_div = tree_page.locator(f"#{children_id}")

        expect(children_div).to_be_visible()
        node_btn.click()
        expect(children_div).to_be_hidden()


# ─────────────────────────────────────────────────────────────
# Unaligned goals section
# ─────────────────────────────────────────────────────────────


class TestGoalTreeUnaligned:
    """The unaligned section behaviour."""

    def test_unaligned_section_present_with_sample_data(self, tree_page: Page) -> None:
        """The sample data includes one parentless team goal, so the
        Niet-gekoppelde doelen section should be visible in the DOM."""
        expect(tree_page.locator("#unaligned-section")).to_have_count(1)

    def test_unaligned_goal_visible(self, tree_page: Page) -> None:
        """The parentless team goal should appear inside the unaligned section."""
        section = tree_page.locator("#unaligned-section")
        expect(section.locator("text=Execute user review and implement UI changes")).to_be_visible()
