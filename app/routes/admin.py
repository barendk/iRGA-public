"""Admin route — entity level management and team-domain assignment.

GET /admin: Display all entities with level dropdowns + team assignment table.
POST /admin: Save level changes and team-domain assignments.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.csrf import verify_csrf
from app.database import get_db
from app.services.entity_service import (
    get_all_entities,
    get_entities_by_level,
    update_entity_levels,
    update_team_assignments,
)
from app.templating import templates

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("", response_class=HTMLResponse)
def admin_entities(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    """Render the admin entity management page."""
    entities = get_all_entities(db)
    domains = get_entities_by_level(db, "domain")
    teams = [e for e in entities if e.level == "team"]

    return templates.TemplateResponse(
        request,
        "admin/entities.html",
        {
            "entities": entities,
            "domains": domains,
            "teams": teams,
            "errors": [],
            "success": False,
        },
    )


@router.post("", response_class=HTMLResponse, dependencies=[Depends(verify_csrf)])
async def admin_save(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    """Save entity level changes and team-domain assignments.

    Async because request.form() requires await (Starlette has no sync
    form parser for dynamic field names). The sync DB session is safe here
    because FastAPI runs sync dependencies in a threadpool.
    """
    form = await request.form()
    all_errors: list[str] = []

    # ── Parse level updates from form ──
    # Form fields: level_{entity_id} = "org"|"domain"|"team"
    level_updates: dict[int, str] = {}
    for key, value in form.items():
        if key.startswith("level_"):
            try:
                entity_id = int(key.removeprefix("level_"))
                level_updates[entity_id] = str(value)
            except ValueError:
                continue

    # ── Parse team-domain assignments from form ──
    # Form fields: parent_{team_id} = domain_id (or "" for none)
    assignments: dict[int, int | None] = {}
    for key, value in form.items():
        if key.startswith("parent_"):
            try:
                team_id = int(key.removeprefix("parent_"))
                domain_id = int(str(value)) if value else None
                assignments[team_id] = domain_id
            except ValueError:
                continue

    # Apply level updates first (affects which entities are domains/teams)
    if level_updates:
        errors = update_entity_levels(db, level_updates)
        all_errors.extend(errors)

    # Apply team-domain assignments
    if assignments and not all_errors:
        errors = update_team_assignments(db, assignments)
        all_errors.extend(errors)

    if all_errors:
        db.rollback()
    else:
        db.commit()

    # Re-fetch entities for display
    entities = get_all_entities(db)
    domains = get_entities_by_level(db, "domain")
    teams = [e for e in entities if e.level == "team"]

    return templates.TemplateResponse(
        request,
        "admin/entities.html",
        {
            "entities": entities,
            "domains": domains,
            "teams": teams,
            "errors": all_errors,
            "success": not all_errors,
        },
    )
