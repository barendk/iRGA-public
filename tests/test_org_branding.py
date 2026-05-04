"""Tests for configurable organisation branding (ORG_NAME, ORG_TAGLINE, ORG_HEADER).

Verifies that the three env-driven branding variables render correctly
in templates — both with custom values and with empty defaults.
"""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.templating import templates


@pytest.fixture()
def _custom_branding() -> Generator[None, None, None]:
    """Temporarily set custom org branding in Jinja2 globals."""
    original = {
        "org_name": templates.env.globals["org_name"],
        "org_tagline": templates.env.globals["org_tagline"],
        "org_header": templates.env.globals["org_header"],
    }
    templates.env.globals["org_name"] = "Test Corp"
    templates.env.globals["org_tagline"] = "Test Corp. Innovation for tomorrow."
    templates.env.globals["org_header"] = "Ministry of Testing"
    yield
    templates.env.globals.update(original)


@pytest.fixture()
def _empty_optional_branding() -> Generator[None, None, None]:
    """Set ORG_NAME but leave tagline and header empty (the default)."""
    original = {
        "org_name": templates.env.globals["org_name"],
        "org_tagline": templates.env.globals["org_tagline"],
        "org_header": templates.env.globals["org_header"],
    }
    templates.env.globals["org_name"] = "Blank Corp"
    templates.env.globals["org_tagline"] = ""
    templates.env.globals["org_header"] = ""
    yield
    templates.env.globals.update(original)


class TestDefaultBranding:
    """With no env vars set, defaults should render."""

    def test_home_title_has_default_org(self, client: TestClient) -> None:
        resp = client.get("/")
        assert "My Organisation" in resp.text

    def test_home_heading_has_default_org(self, client: TestClient) -> None:
        resp = client.get("/")
        assert "My Organisation Goal Review" in resp.text

    def test_header_hidden_when_org_header_empty(self, client: TestClient) -> None:
        """With empty ORG_HEADER, no <h1> ministry name should render in the header."""
        resp = client.get("/")
        header_html = resp.text.split("<header")[1].split("</header>")[0]
        assert "<h1" not in header_html

    def test_footer_hidden_when_org_tagline_empty(self, client: TestClient) -> None:
        """With empty ORG_TAGLINE, no tagline <h3> should render in the footer."""
        resp = client.get("/")
        footer_html = resp.text.split("<footer")[1].split("</footer>")[0]
        assert "font-display italic" not in footer_html


@pytest.mark.usefixtures("_custom_branding")
class TestCustomBranding:
    """With custom env vars, branding should appear throughout."""

    def test_home_title_has_custom_org(self, client: TestClient) -> None:
        resp = client.get("/")
        assert "Test Corp Goal Review" in resp.text

    def test_home_heading_has_custom_org(self, client: TestClient) -> None:
        resp = client.get("/")
        assert "Test Corp Goal Review" in resp.text

    def test_home_description_has_custom_org(self, client: TestClient) -> None:
        resp = client.get("/")
        assert "doelstellingen van Test Corp" in resp.text

    def test_goals_list_title_has_custom_org(self, client: TestClient) -> None:
        resp = client.get("/goals")
        assert "<title>Doelenoverzicht - Test Corp</title>" in resp.text

    def test_goal_tree_title_has_custom_org(self, client: TestClient) -> None:
        resp = client.get("/goals/tree")
        assert "<title>Doelenboom - Test Corp</title>" in resp.text

    def test_strategiekaart_title_has_custom_org(self, client: TestClient) -> None:
        resp = client.get("/goals/map")
        assert "<title>Strategiekaart - Test Corp</title>" in resp.text

    def test_reviews_title_has_custom_org(self, client: TestClient) -> None:
        resp = client.get("/reviews")
        assert "<title>Reviews - Test Corp</title>" in resp.text

    def test_status_title_has_custom_org(self, client: TestClient) -> None:
        resp = client.get("/status")
        assert "<title>PPP Status - Test Corp</title>" in resp.text

    def test_admin_title_has_custom_org(self, client: TestClient) -> None:
        resp = client.get("/admin")
        assert "<title>Admin - Structuurbeheer - Test Corp</title>" in resp.text

    def test_admin_description_has_custom_org(self, client: TestClient) -> None:
        resp = client.get("/admin")
        assert "Test Corp Goal Management System" in resp.text

    def test_header_shows_org_header(self, client: TestClient) -> None:
        resp = client.get("/")
        assert "Ministry of Testing" in resp.text

    def test_footer_shows_org_tagline(self, client: TestClient) -> None:
        resp = client.get("/")
        assert "Test Corp. Innovation for tomorrow." in resp.text

    def test_no_default_org_name_leak(self, client: TestClient) -> None:
        """'My Organisation' should not appear anywhere when custom name is set."""
        resp = client.get("/")
        assert "My Organisation" not in resp.text


@pytest.mark.usefixtures("_empty_optional_branding")
class TestEmptyOptionalBranding:
    """ORG_TAGLINE and ORG_HEADER empty — should be hidden, not blank."""

    def test_org_name_renders(self, client: TestClient) -> None:
        resp = client.get("/")
        assert "Blank Corp Goal Review" in resp.text

    def test_header_no_empty_h1(self, client: TestClient) -> None:
        """No empty <h1> tag should render when org_header is blank."""
        resp = client.get("/")
        # The conditional block should skip rendering entirely
        header_html = resp.text.split("<header")[1].split("</header>")[0]
        assert "<h1" not in header_html

    def test_footer_no_empty_tagline(self, client: TestClient) -> None:
        """No empty <h3> tagline should render when org_tagline is blank."""
        resp = client.get("/")
        footer_html = resp.text.split("<footer")[1].split("</footer>")[0]
        assert "font-display italic" not in footer_html
