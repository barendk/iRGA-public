"""Review service — cycle management, review submission, and data retrieval.

Provides:
  - get_or_create_open_cycles:     auto-seed monthly + quarterly cycles from 2026-01 to today
  - get_goals_for_cycle:           return the goals a team should rate for a given cycle
  - get_existing_review:           fetch a previously submitted MonthlyReview (for pre-fill)
  - get_existing_confidences:      fetch previously submitted GoalConfidence records (for pre-fill)
  - save_review:                   upsert MonthlyReview + GoalConfidence records in one transaction

  PPP Status dashboard aggregation:
  - get_monthly_cycles:            return all monthly cycles ordered most-recent first
  - get_ppp_reviews_for_cycle:     return all MonthlyReview rows for a cycle (with entity loaded)
  - get_confidence_rows_for_cycle: return confidence/goal/entity rows for a cycle
  - get_avg_confidence_for_cycle:  return the mean confidence score for a cycle, or None
  - get_previous_monthly_cycle:    return the monthly cycle for the preceding calendar month
"""

from datetime import UTC, date, datetime

from sqlalchemy.engine import Row
from sqlalchemy.orm import Session, joinedload

from app.models.cycle import ReviewCycle
from app.models.entity import StructuralEntity
from app.models.goal import Goal
from app.models.review import GoalConfidence, MonthlyReview

# Dutch month names used for cycle display names.
_DUTCH_MONTHS = [
    "Januari",
    "Februari",
    "Maart",
    "April",
    "Mei",
    "Juni",
    "Juli",
    "Augustus",
    "September",
    "Oktober",
    "November",
    "December",
]

# First period for which cycles are generated (inclusive).
_START_YEAR = 2026
_START_MONTH = 1  # Januari
_START_QUARTER = 1


# ── Cycle auto-seeding ─────────────────────────────────────────────────────────


def get_or_create_open_cycles(db: Session) -> list[ReviewCycle]:
    """Return all review cycles, auto-creating any that are missing.

    Generates:
      - Monthly cycles from 2026-01 through the current calendar month.
        Name:   "Januari 2026", "Februari 2026", …
        Period: "2026-01", "2026-02", …
      - Quarterly cycles from 2026Q1 through the current calendar quarter.
        Name:   "2026 Q1", "2026 Q2", …
        Period: "2026Q1", "2026Q2", …

    Already-existing cycles are never duplicated; the function is idempotent.
    Newly created cycles default to status "open".

    Returns cycles ordered by period descending (most recent first).
    """
    today = date.today()

    # ── Monthly cycles ──
    year, month = _START_YEAR, _START_MONTH
    while (year, month) <= (today.year, today.month):
        period = f"{year}-{month:02d}"
        name = f"{_DUTCH_MONTHS[month - 1]} {year}"
        _get_or_create_cycle(db, name=name, cycle_type="monthly", period=period)
        month += 1
        if month > 12:
            year += 1
            month = 1

    # ── Quarterly cycles ──
    current_quarter = (today.month - 1) // 3 + 1
    year, quarter = _START_YEAR, _START_QUARTER
    while (year, quarter) <= (today.year, current_quarter):
        period = f"{year}Q{quarter}"
        name = f"{year} Q{quarter}"
        _get_or_create_cycle(db, name=name, cycle_type="quarterly", period=period)
        quarter += 1
        if quarter > 4:
            year += 1
            quarter = 1

    db.commit()

    return db.query(ReviewCycle).order_by(ReviewCycle.period.desc()).all()


def _get_or_create_cycle(db: Session, *, name: str, cycle_type: str, period: str) -> ReviewCycle:
    """Fetch an existing cycle by period+type, or insert a new one."""
    cycle = (
        db.query(ReviewCycle)
        .filter(ReviewCycle.period == period, ReviewCycle.cycle_type == cycle_type)
        .first()
    )
    if cycle is None:
        cycle = ReviewCycle(name=name, cycle_type=cycle_type, period=period, status="open")
        db.add(cycle)
    return cycle


# ── Goal selection ─────────────────────────────────────────────────────────────


def get_goals_for_cycle(db: Session, entity_id: int, cycle: ReviewCycle) -> list[Goal]:
    """Return the goals a team should rate in a given review cycle.

    Monthly cycles: confidence is tracked against the team's quarterly goals.
    The month is mapped to its containing quarter (Jan–Mar = Q1, etc.) and only
    goals with that exact period are returned.

    Quarterly cycles: reserved for Step 10b (quarterly scoring form). Returns
    an empty list for now so the route can show a placeholder.

    Args:
        db:        Database session.
        entity_id: The team's structural entity ID.
        cycle:     The selected ReviewCycle.

    Returns:
        Ordered list of Goal objects for the team and inferred goal period.
    """
    if cycle.cycle_type == "monthly":
        # Parse "YYYY-MM" → infer quarter → build "YYYYQ{n}" goal period.
        year = int(cycle.period[:4])
        month = int(cycle.period[5:7])
        quarter = (month - 1) // 3 + 1
        target_period = f"{year}Q{quarter}"

        return (
            db.query(Goal)
            .filter(
                Goal.entity_id == entity_id,
                Goal.period == target_period,
                Goal.period_type == "quarterly",
            )
            .order_by(Goal.parsed_text)
            .all()
        )

    # Quarterly cycle form is implemented in Step 10b.
    return []


# ── Pre-fill helpers ───────────────────────────────────────────────────────────


def get_existing_review(db: Session, entity_id: int, cycle_id: int) -> MonthlyReview | None:
    """Return the existing MonthlyReview for a team+cycle, or None."""
    return (
        db.query(MonthlyReview)
        .filter(
            MonthlyReview.entity_id == entity_id,
            MonthlyReview.cycle_id == cycle_id,
        )
        .first()
    )


def get_existing_confidences(db: Session, goal_ids: list[int], cycle_id: int) -> dict[int, int]:
    """Return a mapping of goal_id → confidence score for a cycle.

    Only goals that already have a submitted confidence record are included.
    Used to pre-fill the radio buttons when revisiting a form.

    Args:
        db:       Database session.
        goal_ids: The IDs of goals shown in the form.
        cycle_id: The review cycle.

    Returns:
        Dict mapping goal_id to confidence (1–10) for goals with existing scores.
    """
    if not goal_ids:
        return {}

    rows = (
        db.query(GoalConfidence)
        .filter(
            GoalConfidence.goal_id.in_(goal_ids),
            GoalConfidence.cycle_id == cycle_id,
        )
        .all()
    )
    return {row.goal_id: row.confidence for row in rows}


# ── Persistence ────────────────────────────────────────────────────────────────


def save_review(
    db: Session,
    *,
    entity_id: int,
    cycle_id: int,
    progress: str,
    problems: str,
    plans: str,
    support_request: bool,
    confidences: dict[int, int],
) -> MonthlyReview:
    """Upsert a MonthlyReview and all GoalConfidence scores in one transaction.

    If a MonthlyReview already exists for the team+cycle it is updated in place;
    otherwise a new record is created. GoalConfidence records follow the same
    upsert logic per goal.

    Args:
        db:              Database session (caller must not commit separately).
        entity_id:       The team's structural entity ID.
        cycle_id:        The review cycle ID.
        progress:        PPP — progress/wins text.
        problems:        PPP — problems/blockers text.
        plans:           PPP — plans for next period text.
        support_request: True if the team needs support or flags for discussion.
        confidences:     Mapping of goal_id → confidence score (1–10).

    Returns:
        The saved (or updated) MonthlyReview instance.
    """
    now = datetime.now(UTC)

    # ── Upsert MonthlyReview ──
    review = get_existing_review(db, entity_id, cycle_id)
    if review is None:
        review = MonthlyReview(entity_id=entity_id, cycle_id=cycle_id)
        db.add(review)

    review.progress = progress
    review.problems = problems
    review.plans = plans
    review.support_request = support_request
    review.submitted_at = now

    # ── Upsert GoalConfidence for each rated goal ──
    for goal_id, score in confidences.items():
        conf = (
            db.query(GoalConfidence)
            .filter(
                GoalConfidence.goal_id == goal_id,
                GoalConfidence.cycle_id == cycle_id,
            )
            .first()
        )
        if conf is None:
            conf = GoalConfidence(goal_id=goal_id, cycle_id=cycle_id)
            db.add(conf)
        conf.confidence = score
        conf.submitted_at = now

    db.commit()
    return review


# ── PPP Status dashboard aggregation ───────────────────────────────────────────


def get_monthly_cycles(db: Session) -> list[ReviewCycle]:
    """Return all monthly ReviewCycle objects ordered by period descending.

    Periods are stored as "YYYY-MM", so lexicographic descending order equals
    chronological descending order.

    Returns:
        List of monthly ReviewCycle objects, most recent first.
    """
    return (
        db.query(ReviewCycle)
        .filter(ReviewCycle.cycle_type == "monthly")
        .order_by(ReviewCycle.period.desc())
        .all()
    )


def get_ppp_reviews_for_cycle(
    db: Session,
    cycle_id: int,
    domain_id: int | None = None,
) -> list[MonthlyReview]:
    """Return all MonthlyReview records for a given cycle, with entity loaded.

    If domain_id is provided, only reviews from teams that belong to that
    domain (entity.parent_id == domain_id) are returned.

    Args:
        db:        Database session.
        cycle_id:  The review cycle to query.
        domain_id: Optional domain entity ID to restrict results to one domain.

    Returns:
        List of MonthlyReview instances with the `entity` relationship loaded,
        ordered by entity name for consistent display ordering.
    """
    query = (
        db.query(MonthlyReview)
        .join(MonthlyReview.entity)
        .options(joinedload(MonthlyReview.entity))
        .filter(MonthlyReview.cycle_id == cycle_id)
    )

    if domain_id is not None:
        query = query.filter(StructuralEntity.parent_id == domain_id)

    return query.order_by(StructuralEntity.name).all()


def get_confidence_rows_for_cycle(
    db: Session,
    cycle_id: int,
    domain_id: int | None = None,
) -> list[Row[tuple[GoalConfidence, Goal, StructuralEntity]]]:
    """Return (GoalConfidence, Goal, StructuralEntity) tuples for a cycle.

    Each tuple represents one goal's confidence score, together with the goal
    itself and the team (StructuralEntity) that owns that goal.

    If domain_id is provided, only goals owned by teams under that domain are
    returned (team.parent_id == domain_id).

    Args:
        db:        Database session.
        cycle_id:  The review cycle to query.
        domain_id: Optional domain entity ID to restrict results.

    Returns:
        List of (GoalConfidence, Goal, StructuralEntity) tuples ordered by
        entity name then goal parsed_text, for deterministic display ordering.
    """
    query = (
        db.query(GoalConfidence, Goal, StructuralEntity)
        .join(Goal, GoalConfidence.goal_id == Goal.id)
        .join(StructuralEntity, Goal.entity_id == StructuralEntity.id)
        .filter(GoalConfidence.cycle_id == cycle_id)
    )

    if domain_id is not None:
        query = query.filter(StructuralEntity.parent_id == domain_id)

    return query.order_by(StructuralEntity.name, Goal.parsed_text).all()


def get_avg_confidence_for_cycle(db: Session, cycle_id: int) -> float | None:
    """Return the mean confidence score across all goals for a cycle.

    Args:
        db:       Database session.
        cycle_id: The review cycle.

    Returns:
        Average confidence as a float rounded to one decimal place, or None
        if no confidence records exist for the cycle.
    """
    from sqlalchemy import func as sa_func

    result = (
        db.query(sa_func.avg(GoalConfidence.confidence))
        .filter(GoalConfidence.cycle_id == cycle_id)
        .scalar()
    )
    if result is None:
        return None
    return round(float(result), 1)


def get_previous_monthly_cycle(db: Session, current_cycle: ReviewCycle) -> ReviewCycle | None:
    """Return the monthly ReviewCycle for the calendar month before current_cycle.

    Parses the current cycle's period ("YYYY-MM"), decrements the month
    (wrapping December → previous year), and looks up the corresponding cycle.

    Args:
        db:            Database session.
        current_cycle: The cycle whose predecessor we want.

    Returns:
        The preceding monthly ReviewCycle, or None if it does not exist in the
        database (e.g. current_cycle is the very first seeded cycle).
    """
    year = int(current_cycle.period[:4])
    month = int(current_cycle.period[5:7])

    # Decrement month, wrapping January → December of previous year.
    month -= 1
    if month == 0:
        month = 12
        year -= 1

    prev_period = f"{year}-{month:02d}"
    return (
        db.query(ReviewCycle)
        .filter(
            ReviewCycle.cycle_type == "monthly",
            ReviewCycle.period == prev_period,
        )
        .first()
    )
