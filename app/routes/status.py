"""PPP Status dashboard route (/status).

GET /status — Meeting-mode dashboard showing all teams' monthly PPP data
grouped by P-type (Problems, Progress, Plans) plus a Confidence section.

Query params (all optional):
    cycle_id:  ID of the monthly ReviewCycle to display.
               Defaults to the most recent monthly cycle.
    domain_id: Restrict results to teams within this domain entity.
               Empty string (from HTML form) is treated as "no filter".
"""

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.entity_service import get_entities_by_level
from app.services.review_service import (
    get_avg_confidence_for_cycle,
    get_confidence_rows_for_cycle,
    get_monthly_cycles,
    get_or_create_open_cycles,
    get_ppp_reviews_for_cycle,
    get_previous_monthly_cycle,
)
from app.templating import templates

router = APIRouter(prefix="/status", tags=["status"])


@router.get("", response_class=HTMLResponse)
def ppp_status(
    request: Request,
    db: Session = Depends(get_db),
    cycle_id: str | None = Query(default=None),
    domain_id: str | None = Query(default=None),
) -> HTMLResponse:
    """Render the PPP Status dashboard.

    Fetches all monthly reviews and confidence scores for the selected cycle,
    aggregates them into the four dashboard sections, and passes the result
    to the template.

    The 'vs vorige maand' delta is computed by looking up the previous calendar
    month's cycle and comparing average confidence scores.
    """
    # Auto-seed cycles (idempotent) so the dropdown is always populated.
    get_or_create_open_cycles(db)
    monthly_cycles = get_monthly_cycles(db)

    # ── Resolve selected cycle ──────────────────────────────────────────────
    # Default to the most recent monthly cycle when no cycle_id is provided.
    selected_cycle = None
    cycle_id_int: int | None = None

    if cycle_id:
        try:
            cycle_id_int = int(cycle_id)
        except ValueError:
            cycle_id_int = None

    if cycle_id_int is not None:
        # Find the selected cycle in the already-fetched list.
        selected_cycle = next((c for c in monthly_cycles if c.id == cycle_id_int), None)

    # Fall back to most recent cycle if nothing was selected or the id was bad.
    if selected_cycle is None and monthly_cycles:
        selected_cycle = monthly_cycles[0]
        cycle_id_int = selected_cycle.id

    # ── Resolve domain filter ───────────────────────────────────────────────
    domain_id_int: int | None = None
    if domain_id:
        try:
            domain_id_int = int(domain_id)
        except ValueError:
            domain_id_int = None

    # ── Fetch PPP data ──────────────────────────────────────────────────────
    reviews = []
    confidence_rows = []
    avg_confidence: float | None = None
    prev_avg_confidence: float | None = None
    confidence_delta: float | None = None

    if selected_cycle is not None:
        reviews = get_ppp_reviews_for_cycle(db, selected_cycle.id, domain_id_int)
        confidence_rows = get_confidence_rows_for_cycle(db, selected_cycle.id, domain_id_int)

        # Average confidence for the selected cycle.
        avg_confidence = get_avg_confidence_for_cycle(db, selected_cycle.id)

        # Delta: compare to the previous calendar month's cycle.
        prev_cycle = get_previous_monthly_cycle(db, selected_cycle)
        if prev_cycle is not None:
            prev_avg_confidence = get_avg_confidence_for_cycle(db, prev_cycle.id)
        if avg_confidence is not None and prev_avg_confidence is not None:
            confidence_delta = round(avg_confidence - prev_avg_confidence, 1)

    # ── Compute confidence distribution ────────────────────────────────────
    # Buckets match the app-wide traffic-light thresholds:
    #   green  ≥ 7   orange  4–6   red  ≤ 3
    total_scores = len(confidence_rows)
    green_count = sum(1 for conf, _, _ in confidence_rows if conf.confidence >= 7)
    orange_count = sum(1 for conf, _, _ in confidence_rows if 4 <= conf.confidence <= 6)
    red_count = sum(1 for conf, _, _ in confidence_rows if conf.confidence <= 3)

    # Percentage widths for the distribution bars (0 when no data).
    if total_scores > 0:
        green_pct = round(green_count / total_scores * 100)
        orange_pct = round(orange_count / total_scores * 100)
        red_pct = round(red_count / total_scores * 100)
    else:
        green_pct = orange_pct = red_pct = 0

    # Count of teams that submitted reviews (support_request or not).
    submitted_team_count = len(reviews)

    # Count of teams that escalated (flagged support request).
    escalated_count = sum(1 for r in reviews if r.support_request)

    # ── Fetch sidebar dropdown options ──────────────────────────────────────
    domains = get_entities_by_level(db, "domain")

    return templates.TemplateResponse(
        request,
        "status/index.html",
        {
            "monthly_cycles": monthly_cycles,
            "selected_cycle": selected_cycle,
            "domains": domains,
            "current_domain_id": domain_id_int,
            # PPP review cards (same list, template splits by section).
            "reviews": reviews,
            # Confidence table rows: list of (GoalConfidence, Goal, StructuralEntity).
            "confidence_rows": confidence_rows,
            # Confidence stats.
            "avg_confidence": avg_confidence,
            "confidence_delta": confidence_delta,
            "submitted_team_count": submitted_team_count,
            "escalated_count": escalated_count,
            "green_count": green_count,
            "orange_count": orange_count,
            "red_count": red_count,
            "green_pct": green_pct,
            "orange_pct": orange_pct,
            "red_pct": red_pct,
            "total_scores": total_scores,
        },
    )
