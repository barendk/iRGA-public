"""TSV import service — two-pass import of GitHub Projects export.

Pass 1: Create/update structural entities and goals (no parent links).
Pass 2: Link parent relationships using GitHub URLs.

The TSV format has columns:
  Title, URL, Assignees, Status, Sub-issues progress, Parent issue, Start Date
"""

import csv
import re
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.entity import StructuralEntity
from app.models.goal import Goal
from app.services.title_parser import parse_title


@dataclass
class ImportResult:
    """Summary of an import operation."""

    entities_created: int = 0
    entities_seen: int = 0
    goals_created: int = 0
    goals_updated: int = 0
    parent_links_set: int = 0
    entities_created_names: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _extract_issue_id(github_url: str) -> int | None:
    """Extract the issue number from a GitHub URL.

    Example: "https://github.com/org/repo/issues/123" → 123
    """
    match = re.search(r"/issues/(\d+)$", github_url)
    return int(match.group(1)) if match else None


def _find_or_create_entity(db: Session, name: str, result: ImportResult) -> StructuralEntity:
    """Find an existing entity by name, or create a new one.

    Tracks created vs seen (already existing) entities separately.
    """
    result.entities_seen += 1
    entity = db.query(StructuralEntity).filter(StructuralEntity.name == name).first()
    if entity is None:
        entity = StructuralEntity(name=name)
        db.add(entity)
        db.flush()  # Get the ID
        result.entities_created += 1
        result.entities_created_names.append(name)
    return entity


def _upsert_goal(
    db: Session,
    *,
    title: str,
    parsed_text: str | None,
    github_url: str | None,
    github_issue_id: int | None,
    owner: str | None,
    period: str | None,
    period_type: str | None,
    status: str | None,
    entity: StructuralEntity,
    result: ImportResult,
) -> Goal:
    """Create or update a goal, matched by github_url."""
    goal = None
    if github_url:
        goal = db.query(Goal).filter(Goal.github_url == github_url).first()

    if goal is None:
        goal = Goal(
            title=title,
            parsed_text=parsed_text,
            github_url=github_url,
            github_issue_id=github_issue_id,
            owner=owner,
            period=period,
            period_type=period_type,
            status=status,
            entity_id=entity.id,
            goal_level=entity.level,
        )
        db.add(goal)
        result.goals_created += 1
    else:
        # Update existing goal
        goal.title = title
        goal.parsed_text = parsed_text
        goal.owner = owner
        goal.period = period
        goal.period_type = period_type
        goal.status = status
        goal.entity_id = entity.id
        goal.goal_level = entity.level
        result.goals_updated += 1

    db.flush()
    return goal


def import_goals_from_tsv(db: Session, tsv_path: str | Path) -> ImportResult:
    """Import goals from a GitHub Projects TSV export.

    Two-pass algorithm:
      Pass 1: Create/update entities and goals (no parent links)
      Pass 2: Link parent relationships using GitHub URLs

    Args:
        db: SQLAlchemy database session
        tsv_path: Path to the TSV file

    Returns:
        ImportResult with counts and any warnings
    """
    tsv_path = Path(tsv_path)
    result = ImportResult()

    with open(tsv_path, encoding="utf-8") as f:
        content = f.read()

    rows = list(csv.DictReader(StringIO(content), delimiter="\t"))

    # Map GitHub URL → Goal (populated in pass 1, used in pass 2)
    url_to_goal: dict[str, Goal] = {}

    # ── Pass 1: Create entities and goals ──
    for i, row in enumerate(rows, start=2):  # start=2 because row 1 is header
        title = row.get("Title", "").strip()
        if not title:
            result.warnings.append(f"Rij {i}: Lege titel, overgeslagen.")
            continue

        parsed = parse_title(title)
        github_url = row.get("URL", "").strip() or None
        assignees = row.get("Assignees", "").strip() or None
        status = row.get("Status", "").strip() or None

        # Always ensure the structural entity exists
        entity = _find_or_create_entity(db, parsed.unit_name, result)

        if parsed.is_goal:
            # This is a goal — create/update it
            github_issue_id = _extract_issue_id(github_url) if github_url else None
            goal = _upsert_goal(
                db,
                title=title,
                parsed_text=parsed.goal_text,
                github_url=github_url,
                github_issue_id=github_issue_id,
                owner=assignees,
                period=parsed.period,
                period_type=parsed.period_type,
                status=status,
                entity=entity,
                result=result,
            )
            if github_url:
                url_to_goal[github_url] = goal
        else:
            # Structural entity only — no goal to create
            # But register URL mapping if it has one (for parent linking)
            pass

    # ── Pass 2: Link parent relationships ──
    for i, row in enumerate(rows, start=2):
        parent_url = row.get("Parent issue", "").strip()
        github_url = row.get("URL", "").strip()

        if not parent_url or not github_url:
            continue

        # Find the child goal
        child_goal = url_to_goal.get(github_url)
        if child_goal is None:
            continue

        # Find the parent goal
        parent_goal = url_to_goal.get(parent_url)
        if parent_goal is None:
            # Parent might already exist in DB from a previous import
            parent_goal = db.query(Goal).filter(Goal.github_url == parent_url).first()

        if parent_goal is not None:
            child_goal.parent_goal_id = parent_goal.id
            result.parent_links_set += 1
        else:
            result.warnings.append(
                f"Rij {i}: Bovenliggend doel niet gevonden voor URL {parent_url}"
            )

    db.flush()
    return result
