"""Goals routes — list view (/goals) and tree view (/goals/tree)."""

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.entity_service import get_entities_by_level
from app.services.goal_service import (
    build_goal_tree,
    build_map_groups,
    compute_goal_stats,
    get_distinct_periods,
    get_goals_filtered,
    get_latest_confidence,
)
from app.templating import templates

router = APIRouter(prefix="/goals", tags=["goals"])


@router.get("", response_class=HTMLResponse)
def goals_list(
    request: Request,
    db: Session = Depends(get_db),
    period: str = Query(default=""),
    levels: list[str] = Query(default=["org", "domain", "team"]),
    goal_types: list[str] = Query(default=["yearly", "quarterly"]),
    domain_id: str | None = Query(default=None),
) -> HTMLResponse:
    """Render the goals list view with optional server-side filtering.

    Query params (all optional — omit any to include all):
        period: Specific period string, e.g. "2026Q1" or "2026". Empty = all.
        levels: Goal levels to show. Repeat param: ?levels=org&levels=domain.
            Default: all three (org, domain, team).
        goal_types: Period types to show ("yearly" and/or "quarterly").
            Default: both.
        domain_id: Restrict to a specific domain entity. Submitted as a string
            by the HTML form (empty string when "Alle Domeinen" is selected).
    """
    # Convert domain_id from form string to int — empty string means "no filter".
    domain_id_int: int | None = None
    if domain_id:
        try:
            domain_id_int = int(domain_id)
        except ValueError:
            domain_id_int = None

    # ── Fetch filtered goals ──
    goals_by_level = get_goals_filtered(
        db,
        period=period or None,
        levels=levels or None,
        goal_types=goal_types or None,
        domain_id=domain_id_int,
    )

    # ── Fetch latest confidence per goal (one query per goal — N+1 OK for MVP) ──
    all_goals = goals_by_level["org"] + goals_by_level["domain"] + goals_by_level["team"]
    confidences = {goal.id: get_latest_confidence(db, goal.id) for goal in all_goals}

    # ── Compute summary stats ──
    stats = compute_goal_stats(goals_by_level, confidences)

    # ── Fetch filter dropdown options ──
    domains = get_entities_by_level(db, "domain")
    periods = get_distinct_periods(db)

    return templates.TemplateResponse(
        request,
        "goals/list.html",
        {
            "goals_by_level": goals_by_level,
            "confidences": confidences,
            "stats": stats,
            "domains": domains,
            "periods": periods,
            # Current filter state — used to restore the form on page reload.
            "current_period": period,
            "current_levels": set(levels),
            "current_goal_types": set(goal_types),
            "current_domain_id": domain_id_int,
        },
    )


@router.get("/tree", response_class=HTMLResponse)
def goals_tree(
    request: Request,
    db: Session = Depends(get_db),
    period_type_toggle: str = Query(default="quarterly"),
    period: str = Query(default=""),
    level: str = Query(default=""),
    domain_id: str | None = Query(default=None),
) -> HTMLResponse:
    """Render the goal tree view with collapsible hierarchy.

    Query params (all optional):
        period_type_toggle: "quarterly" or "yearly". Default "quarterly".
        period: Specific period string, e.g. "2026Q1". Empty = all.
        level: Single level filter: "org", "domain", or "team". Empty = all.
        domain_id: Restrict to a domain (same semantics as goals_list).
    """
    # Convert domain_id from form string to int.
    domain_id_int: int | None = None
    if domain_id:
        try:
            domain_id_int = int(domain_id)
        except ValueError:
            domain_id_int = None

    # A single level dropdown maps to a one-element list (or None for all).
    levels: list[str] | None = [level] if level else None

    # Normalise invalid values to the default so the template always receives a
    # valid period_type (prevents the hidden input from carrying garbage forward).
    if period_type_toggle not in ("quarterly", "yearly"):
        period_type_toggle = "quarterly"
    goal_types = [period_type_toggle]

    # ── Fetch filtered goals ──
    goals_by_level = get_goals_filtered(
        db,
        period=period or None,
        levels=levels,
        goal_types=goal_types,
        domain_id=domain_id_int,
    )

    # ── Fetch latest confidence per goal (N+1 — acceptable for MVP) ──
    all_goals = goals_by_level["org"] + goals_by_level["domain"] + goals_by_level["team"]
    confidences = {g.id: get_latest_confidence(db, g.id) for g in all_goals}

    # ── Build the tree structure ──
    roots, unaligned = build_goal_tree(all_goals, confidences)

    # ── Fetch filter dropdown options ──
    domains = get_entities_by_level(db, "domain")
    periods = get_distinct_periods(db)

    return templates.TemplateResponse(
        request,
        "goals/tree.html",
        {
            "roots": roots,
            "unaligned": unaligned,
            "domains": domains,
            "periods": periods,
            # Current filter state — used to restore the form on page reload.
            "current_period_type": period_type_toggle,
            "current_period": period,
            "current_level": level,
            "current_domain_id": domain_id_int,
        },
    )


@router.get("/map", response_class=HTMLResponse)
def goals_map(
    request: Request,
    db: Session = Depends(get_db),
    period_type_toggle: str = Query(default="quarterly"),
    period: str = Query(default=""),
    domain_id: str | None = Query(default=None),
) -> HTMLResponse:
    """Render the Strategiekaart view — 3-layer visual canvas.

    Goals are arranged in three horizontal rows (org → domain → team) with
    CSS connector lines within each parent-group column.  Each org goal anchors
    a column of its domain children; each domain goal anchors a column of its
    team children.  Domain and team goals with no parent in the current filter
    are rendered as free columns/cards without connectors.

    Query params (all optional):
        period_type_toggle: "quarterly" or "yearly". Default "quarterly".
        period: Specific period string, e.g. "2026Q1". Empty = all.
        domain_id: Restrict to a domain entity (same semantics as goals_list).
    """
    # Convert domain_id from form string to int.
    domain_id_int: int | None = None
    if domain_id:
        try:
            domain_id_int = int(domain_id)
        except ValueError:
            domain_id_int = None

    # Normalise invalid period_type values to the default.
    if period_type_toggle not in ("quarterly", "yearly"):
        period_type_toggle = "quarterly"
    goal_types = [period_type_toggle]

    # ── Fetch filtered goals ──
    goals_by_level = get_goals_filtered(
        db,
        period=period or None,
        goal_types=goal_types,
        domain_id=domain_id_int,
    )

    # ── Fetch latest confidence per goal (N+1 — acceptable for MVP) ──
    all_goals = goals_by_level["org"] + goals_by_level["domain"] + goals_by_level["team"]
    confidences = {g.id: get_latest_confidence(db, g.id) for g in all_goals}

    # ── Build the column-group structure for the canvas ──
    org_groups, free_domain_groups, free_teams = build_map_groups(goals_by_level, confidences)

    # ── Fetch filter dropdown options ──
    domains = get_entities_by_level(db, "domain")
    periods = get_distinct_periods(db)

    return templates.TemplateResponse(
        request,
        "goals/map.html",
        {
            "org_groups": org_groups,
            "free_domain_groups": free_domain_groups,
            "free_teams": free_teams,
            "domains": domains,
            "periods": periods,
            # Current filter state — used to restore the form on page reload.
            "current_period_type": period_type_toggle,
            "current_period": period,
            "current_domain_id": domain_id_int,
        },
    )
