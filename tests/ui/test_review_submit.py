"""Playwright UI tests for review submission (/reviews POST).

Tests the full submit flow: fill form → confirmation page, pre-fill
on revisit, and Dutch validation errors when required fields are missing.

Test isolation strategy:
  - TestReviewSubmitSuccess uses Team Alpha  (Januari 2026)
  - TestReviewPrefill       uses Team Beta   (Februari 2026)
  - TestReviewValidation    uses Team Gamma  (Januari 2026, never successfully submitted)
    Gamma has 1 goal for 2026Q1 so confidence error count is predictable.
"""

import re

import pytest
from playwright.sync_api import Page, expect

# ── Shared helpers ─────────────────────────────────────────────────────────────


def _open_review_form(page: Page, base_url: str, team: str, cycle: str) -> None:
    """Navigate to /reviews and select a team + cycle, then click Tonen."""
    page.goto(f"{base_url}/reviews")
    page.locator("[data-testid='entity-select']").select_option(label=team)
    page.locator("[data-testid='cycle-select']").select_option(label=cycle)
    page.locator("button", has_text="Tonen").click()
    page.wait_for_load_state("networkidle")


def _fill_ppp(page: Page) -> None:
    """Fill all three PPP textareas with valid test content."""
    page.locator("[data-testid='progress-textarea']").fill("We launched the new auth module.")
    page.locator("[data-testid='problems-textarea']").fill(
        "Database migration took longer than expected."
    )
    page.locator("[data-testid='plans-textarea']").fill(
        "Finish schema migration and write runbooks."
    )


def _select_all_confidences(page: Page, value: str = "7") -> None:
    """Select a confidence score for every goal shown in the form.

    Radio buttons use the sr-only pattern (hidden from layout; the <label>
    is the visible target). We use check(force=True) to bypass Playwright's
    pointer-event actionability check on the hidden inputs.
    """
    radios = page.locator(f"input[type='radio'][name^='confidence_'][value='{value}']")
    count = radios.count()
    for i in range(count):
        radios.nth(i).check(force=True)


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture()
def filled_form_page(ui_page: Page, base_url: str) -> Page:
    """Open Team Alpha review form (Januari 2026), fill it, return without submitting."""
    _open_review_form(ui_page, base_url, "Team Alpha", "Januari 2026")
    _fill_ppp(ui_page)
    _select_all_confidences(ui_page)
    return ui_page


# ── Successful submit ──────────────────────────────────────────────────────────


class TestReviewSubmitSuccess:
    """Test that a fully filled form submits and shows the confirmation page."""

    def test_submit_redirects_to_confirmation(self, filled_form_page: Page) -> None:
        filled_form_page.locator("[data-testid='submit-btn']").click()
        filled_form_page.wait_for_load_state("networkidle")
        expect(filled_form_page).to_have_url(re.compile(r"/reviews/confirmation"))

    def test_confirmation_page_shows_success_heading(self, filled_form_page: Page) -> None:
        filled_form_page.locator("[data-testid='submit-btn']").click()
        filled_form_page.wait_for_load_state("networkidle")
        expect(filled_form_page.locator("h2", has_text="Review ingediend!")).to_be_visible()

    def test_confirmation_page_shows_team_name(self, filled_form_page: Page) -> None:
        filled_form_page.locator("[data-testid='submit-btn']").click()
        filled_form_page.wait_for_load_state("networkidle")
        expect(filled_form_page.locator("text=Team Alpha")).to_be_visible()

    def test_confirmation_page_shows_cycle_name(self, filled_form_page: Page) -> None:
        filled_form_page.locator("[data-testid='submit-btn']").click()
        filled_form_page.wait_for_load_state("networkidle")
        expect(filled_form_page.locator("text=Januari 2026")).to_be_visible()

    def test_confirmation_has_back_link(self, filled_form_page: Page) -> None:
        """Confirmation page should offer a link back to the reviews index."""
        filled_form_page.locator("[data-testid='submit-btn']").click()
        filled_form_page.wait_for_load_state("networkidle")
        link = filled_form_page.locator("a", has_text="Andere review invullen")
        expect(link).to_be_visible()


# ── Pre-fill on revisit ────────────────────────────────────────────────────────


class TestReviewPrefill:
    """Test that previously saved values are pre-filled when revisiting the form.

    Uses Team Beta (Februari 2026) — isolated from TestReviewSubmitSuccess.
    """

    def test_ppp_fields_prefilled_after_submit(self, ui_page: Page, base_url: str) -> None:
        """Submit a review then revisit via 'Review bewerken' — PPP should be pre-filled."""
        _open_review_form(ui_page, base_url, "Team Beta", "Februari 2026")

        ui_page.locator("[data-testid='progress-textarea']").fill("Completed CI/CD pipeline.")
        ui_page.locator("[data-testid='problems-textarea']").fill("Runbook gaps identified.")
        ui_page.locator("[data-testid='plans-textarea']").fill("Close runbook gaps next sprint.")
        _select_all_confidences(ui_page, value="8")

        ui_page.locator("[data-testid='submit-btn']").click()
        ui_page.wait_for_load_state("networkidle")

        # Revisit the form using the "Review bewerken" link on the confirmation page.
        ui_page.locator("a", has_text="Review bewerken").click()
        ui_page.wait_for_load_state("networkidle")

        expect(ui_page.locator("[data-testid='progress-textarea']")).to_have_value(
            "Completed CI/CD pipeline."
        )
        expect(ui_page.locator("[data-testid='problems-textarea']")).to_have_value(
            "Runbook gaps identified."
        )
        expect(ui_page.locator("[data-testid='plans-textarea']")).to_have_value(
            "Close runbook gaps next sprint."
        )

    def test_confidence_scores_prefilled_after_submit(self, ui_page: Page, base_url: str) -> None:
        """After submitting confidence 8, revisiting shows the radios pre-checked.

        Submits the form explicitly (no reliance on a sibling test having run first).
        Team Beta has 2 goals for 2026Q1, so 2 radios with value=8 should be checked.
        """
        _open_review_form(ui_page, base_url, "Team Beta", "Februari 2026")

        ui_page.locator("[data-testid='progress-textarea']").fill("Completed CI/CD pipeline.")
        ui_page.locator("[data-testid='problems-textarea']").fill("Runbook gaps identified.")
        ui_page.locator("[data-testid='plans-textarea']").fill("Close runbook gaps next sprint.")
        _select_all_confidences(ui_page, value="8")

        ui_page.locator("[data-testid='submit-btn']").click()
        ui_page.wait_for_load_state("networkidle")

        # Revisit the form — confidence radios should be pre-checked from the DB.
        ui_page.locator("a", has_text="Review bewerken").click()
        ui_page.wait_for_load_state("networkidle")

        checked_radios = ui_page.locator(
            "input[type='radio'][name^='confidence_'][value='8']:checked"
        )
        expect(checked_radios).to_have_count(2)


# ── Validation errors ──────────────────────────────────────────────────────────


class TestReviewValidation:
    """Test that submitting with missing fields shows Dutch error messages.

    Uses Team Gamma (Januari 2026) throughout — it has exactly 1 goal for 2026Q1
    and is never successfully submitted, so there is no pre-fill to interfere.
    """

    def _open_gamma(self, page: Page, base_url: str) -> None:
        _open_review_form(page, base_url, "Team Gamma", "Januari 2026")

    def test_empty_submit_shows_errors(self, ui_page: Page, base_url: str) -> None:
        """Submitting with nothing filled should show the error banner."""
        self._open_gamma(ui_page, base_url)
        ui_page.locator("[data-testid='submit-btn']").click()
        ui_page.wait_for_load_state("networkidle")

        expect(ui_page.locator("[data-testid='error-banner']")).to_be_visible()

    def test_missing_progress_shows_dutch_error(self, ui_page: Page, base_url: str) -> None:
        self._open_gamma(ui_page, base_url)
        ui_page.locator("[data-testid='progress-textarea']").fill("")  # ensure empty
        ui_page.locator("[data-testid='problems-textarea']").fill("Some problems.")
        ui_page.locator("[data-testid='plans-textarea']").fill("Some plans.")
        _select_all_confidences(ui_page)
        ui_page.locator("[data-testid='submit-btn']").click()
        ui_page.wait_for_load_state("networkidle")

        expect(ui_page.locator("text=Voortgang is verplicht.")).to_be_visible()

    def test_missing_problems_shows_dutch_error(self, ui_page: Page, base_url: str) -> None:
        self._open_gamma(ui_page, base_url)
        ui_page.locator("[data-testid='progress-textarea']").fill("Some progress.")
        ui_page.locator("[data-testid='problems-textarea']").fill("")  # ensure empty
        ui_page.locator("[data-testid='plans-textarea']").fill("Some plans.")
        _select_all_confidences(ui_page)
        ui_page.locator("[data-testid='submit-btn']").click()
        ui_page.wait_for_load_state("networkidle")

        expect(ui_page.locator("text=Problemen is verplicht.")).to_be_visible()

    def test_missing_plans_shows_dutch_error(self, ui_page: Page, base_url: str) -> None:
        self._open_gamma(ui_page, base_url)
        ui_page.locator("[data-testid='progress-textarea']").fill("Some progress.")
        ui_page.locator("[data-testid='problems-textarea']").fill("Some problems.")
        ui_page.locator("[data-testid='plans-textarea']").fill("")  # ensure empty
        _select_all_confidences(ui_page)
        ui_page.locator("[data-testid='submit-btn']").click()
        ui_page.wait_for_load_state("networkidle")

        expect(ui_page.locator("text=Plannen is verplicht.")).to_be_visible()

    def test_missing_confidence_shows_dutch_error(self, ui_page: Page, base_url: str) -> None:
        """Submitting without selecting a confidence score should show an error per goal."""
        self._open_gamma(ui_page, base_url)
        _fill_ppp(ui_page)
        # Deliberately omit confidence selection
        ui_page.locator("[data-testid='submit-btn']").click()
        ui_page.wait_for_load_state("networkidle")

        # Team Gamma has 1 goal → 1 confidence error
        error_items = ui_page.locator("[data-testid='error-banner'] li")
        expect(error_items).to_have_count(1)

    def test_form_values_preserved_on_validation_error(self, ui_page: Page, base_url: str) -> None:
        """After a failed submit, the filled PPP fields should still be present."""
        self._open_gamma(ui_page, base_url)
        _fill_ppp(ui_page)
        # Omit confidence to trigger validation failure
        ui_page.locator("[data-testid='submit-btn']").click()
        ui_page.wait_for_load_state("networkidle")

        expect(ui_page.locator("[data-testid='progress-textarea']")).to_have_value(
            "We launched the new auth module."
        )
