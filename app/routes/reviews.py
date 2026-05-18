"""Reviews route — monthly review entry form (/reviews).

GET  /reviews                — Empty state (no params) or pre-filled form
                               (entity_id + cycle_id query params).
POST /reviews                — Validate and save monthly review, then redirect.
GET  /reviews/confirmation   — Thank-you page shown after a successful submit.
"""

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from app.csrf import verify_csrf
from app.database import get_db
from app.models.cycle import ReviewCycle
from app.models.entity import StructuralEntity
from app.models.review import MonthlyReview
from app.services.entity_service import get_entities_by_level
from app.services.review_service import (
    get_existing_confidences,
    get_existing_review,
    get_goals_for_cycle,
    get_or_create_open_cycles,
    save_review,
)
from app.templating import templates

router = APIRouter(prefix="/reviews", tags=["reviews"])


# ── Helper ─────────────────────────────────────────────────────────────────────


def _render_form(
    request: Request,
    *,
    teams: list[StructuralEntity],
    cycles: list[ReviewCycle],
    selected_entity: StructuralEntity | None,
    selected_cycle: ReviewCycle | None,
    goals: list,
    prefill: dict,
    errors: list[str],
) -> HTMLResponse:
    """Render reviews/enter.html with the given context.

    Centralises all the template context building so both GET and the
    failed-validation POST path use the same logic.
    """
    return templates.TemplateResponse(
        request,
        "reviews/enter.html",
        {
            "teams": teams,
            "cycles": cycles,
            "selected_entity": selected_entity,
            "selected_cycle": selected_cycle,
            "goals": goals,
            "prefill": prefill,
            "errors": errors,
        },
    )


# ── GET /reviews ───────────────────────────────────────────────────────────────


@router.get("", response_class=HTMLResponse)
def reviews_form(
    request: Request,
    db: Session = Depends(get_db),
    entity_id: str | None = Query(default=None),
    cycle_id: str | None = Query(default=None),
) -> HTMLResponse:
    """Render the review form.

    With no query params → empty state ("select a team and period first").
    With entity_id + cycle_id → full form, pre-filled with any existing data.
    """
    # Auto-seed cycles and fetch dropdown data.
    cycles = get_or_create_open_cycles(db)
    teams = get_entities_by_level(db, "team")

    # Parse optional IDs; treat empty strings or invalid values as None.
    entity_id_int = _parse_int(entity_id)
    cycle_id_int = _parse_int(cycle_id)

    if entity_id_int is None or cycle_id_int is None:
        # No selection yet — show empty state.
        return _render_form(
            request,
            teams=teams,
            cycles=cycles,
            selected_entity=None,
            selected_cycle=None,
            goals=[],
            prefill={},
            errors=[],
        )

    # Look up selected team and cycle.
    selected_entity = db.get(StructuralEntity, entity_id_int)
    selected_cycle = db.get(ReviewCycle, cycle_id_int)

    if selected_entity is None or selected_cycle is None:
        # Invalid IDs — fall back to empty state.
        return _render_form(
            request,
            teams=teams,
            cycles=cycles,
            selected_entity=None,
            selected_cycle=None,
            goals=[],
            prefill={},
            errors=["Ongeldig team of reviewperiode geselecteerd."],
        )

    goals = get_goals_for_cycle(db, entity_id_int, selected_cycle)

    # Build pre-fill dict from any previously saved review.
    existing_review = get_existing_review(db, entity_id_int, cycle_id_int)
    existing_confs = get_existing_confidences(db, [g.id for g in goals], cycle_id_int)

    prefill = _build_prefill(existing_review, existing_confs)

    return _render_form(
        request,
        teams=teams,
        cycles=cycles,
        selected_entity=selected_entity,
        selected_cycle=selected_cycle,
        goals=goals,
        prefill=prefill,
        errors=[],
    )


# ── POST /reviews ──────────────────────────────────────────────────────────────


MAX_PPP_LEN = 5_000  # characters


@router.post("", response_model=None, dependencies=[Depends(verify_csrf)])
async def reviews_submit(
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    """Validate and save a monthly review, then redirect to the confirmation page.

    Form fields expected:
        entity_id        — team entity ID (hidden)
        cycle_id         — review cycle ID (hidden)
        progress         — PPP: wins/accomplishments (required)
        problems         — PPP: blockers/challenges (required)
        plans            — PPP: plans for next period (required)
        support_request  — checkbox, present = True
        confidence_{id}  — one field per goal, value 1–10 (all required)
    """
    form = await request.form()

    entity_id_int = _parse_int(str(form.get("entity_id", "")))
    cycle_id_int = _parse_int(str(form.get("cycle_id", "")))

    # Always re-fetch cycles and teams for re-rendering on error.
    cycles = get_or_create_open_cycles(db)
    teams = get_entities_by_level(db, "team")

    selected_entity = db.get(StructuralEntity, entity_id_int) if entity_id_int else None
    selected_cycle = db.get(ReviewCycle, cycle_id_int) if cycle_id_int else None

    goals = (
        get_goals_for_cycle(db, entity_id_int, selected_cycle)
        if (entity_id_int and selected_cycle)
        else []
    )

    # ── Parse submitted values ──
    progress = str(form.get("progress", "")).strip()
    problems = str(form.get("problems", "")).strip()
    plans = str(form.get("plans", "")).strip()
    support_request = "support_request" in form

    # Parse per-goal confidence scores — form field names: confidence_{goal_id}
    submitted_confs: dict[int, int] = {}
    for goal in goals:
        raw = str(form.get(f"confidence_{goal.id}", "")).strip()
        if raw.isdigit():
            val = int(raw)
            if 1 <= val <= 10:
                submitted_confs[goal.id] = val

    # ── Validate ──
    errors: list[str] = []
    if not progress:
        errors.append("Voortgang is verplicht.")
    elif len(progress) > MAX_PPP_LEN:
        errors.append(f"Voortgang mag maximaal {MAX_PPP_LEN:,} tekens bevatten.")
    if not problems:
        errors.append("Problemen is verplicht.")
    elif len(problems) > MAX_PPP_LEN:
        errors.append(f"Problemen mag maximaal {MAX_PPP_LEN:,} tekens bevatten.")
    if not plans:
        errors.append("Plannen is verplicht.")
    elif len(plans) > MAX_PPP_LEN:
        errors.append(f"Plannen mag maximaal {MAX_PPP_LEN:,} tekens bevatten.")
    for goal in goals:
        if goal.id not in submitted_confs:
            errors.append(f"Vertrouwensscore voor '{goal.parsed_text or goal.title}' is verplicht.")

    if errors:
        # Re-render the form with submitted values preserved.
        prefill = {
            "progress": progress,
            "problems": problems,
            "plans": plans,
            "support_request": support_request,
            "confidences": submitted_confs,
        }
        return _render_form(
            request,
            teams=teams,
            cycles=cycles,
            selected_entity=selected_entity,
            selected_cycle=selected_cycle,
            goals=goals,
            prefill=prefill,
            errors=errors,
        )

    # ── Save ──
    # entity_id_int / cycle_id_int are None only when the form is submitted
    # without hidden fields, which cannot happen via the normal UI.
    assert entity_id_int is not None and cycle_id_int is not None
    save_review(
        db,
        entity_id=entity_id_int,
        cycle_id=cycle_id_int,
        progress=progress,
        problems=problems,
        plans=plans,
        support_request=support_request,
        confidences=submitted_confs,
    )

    return RedirectResponse(
        url=f"/reviews/confirmation?entity_id={entity_id_int}&cycle_id={cycle_id_int}",
        status_code=303,
    )


# ── GET /reviews/confirmation ──────────────────────────────────────────────────


@router.get("/confirmation", response_class=HTMLResponse)
def reviews_confirmation(
    request: Request,
    db: Session = Depends(get_db),
    entity_id: str | None = Query(default=None),
    cycle_id: str | None = Query(default=None),
) -> HTMLResponse:
    """Render the post-submit confirmation page."""
    entity_id_int = _parse_int(entity_id)
    cycle_id_int = _parse_int(cycle_id)

    selected_entity = db.get(StructuralEntity, entity_id_int) if entity_id_int else None
    selected_cycle = db.get(ReviewCycle, cycle_id_int) if cycle_id_int else None

    return templates.TemplateResponse(
        request,
        "reviews/confirmation.html",
        {
            "selected_entity": selected_entity,
            "selected_cycle": selected_cycle,
        },
    )


# ── Utilities ──────────────────────────────────────────────────────────────────


def _parse_int(value: str | None) -> int | None:
    """Parse a string to int, returning None on failure or empty input."""
    if not value:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _build_prefill(
    review: MonthlyReview | None,
    confs: dict[int, int],
) -> dict:
    """Build a pre-fill dict from an existing review and confidence records."""
    if review is None:
        return {"confidences": confs}
    return {
        "progress": review.progress or "",
        "problems": review.problems or "",
        "plans": review.plans or "",
        "support_request": review.support_request,
        "confidences": confs,
    }
