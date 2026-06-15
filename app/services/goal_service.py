"""Goal service — filter, aggregate, and structure goals.

Provides:
  - get_goals_filtered: query goals with optional filters, grouped by level
  - get_distinct_periods: return all distinct (period, period_type) pairs
  - get_latest_confidence: return most recent GoalConfidence for a goal
  - compute_goal_stats: compute summary stats from pre-fetched confidences
  - GoalNode: dataclass representing a node in the goal hierarchy tree
  - build_goal_tree: build a tree from a flat filtered goal list
"""

from dataclasses import dataclass

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.entity import StructuralEntity
from app.models.goal import Goal
from app.models.review import GoalConfidence


@dataclass
class GoalStats:
    """Summary statistics for the goals list header cards."""

    total: int
    hoog_vertrouwen: int  # goals with latest confidence >= 7 (green)
    aandacht_nodig: int  # goals with latest confidence <= 3 (red)


def get_goals_filtered(
    db: Session,
    *,
    period: str | None = None,
    levels: list[str] | None = None,
    goal_types: list[str] | None = None,
    domain_id: int | None = None,
) -> dict[str, list[Goal]]:
    """Query goals with optional filters, returned grouped by level.

    Filters are ANDed together; omitting a filter means "include all".

    Args:
        db: Database session.
        period: Specific period string (e.g. "2026Q1"), or None for all.
        levels: Goal levels to include ("org", "domain", "team"), None = all.
        goal_types: Period types to include ("yearly", "quarterly"), None = all.
        domain_id: Scope to a domain — includes org goals + that domain's goals
                   + goals of all teams under that domain.

    Returns:
        Dict with keys "org", "domain", "team", each a list of matching goals.
        Goals with no goal_level set are excluded.
    """
    query = db.query(Goal).join(Goal.entity, isouter=True)

    if period:
        query = query.filter(Goal.period == period)

    if goal_types:
        query = query.filter(Goal.period_type.in_(goal_types))

    if domain_id is not None:
        # Show org goals always, plus the domain's own goals and its teams' goals.
        query = query.filter(
            or_(
                StructuralEntity.level == "org",
                StructuralEntity.id == domain_id,
                StructuralEntity.parent_id == domain_id,
            )
        )

    all_goals = query.order_by(Goal.period, Goal.parsed_text).all()

    # Apply level filter in Python — avoids complex SQL for the tiny MVP dataset.
    # Use goal.entity.level (current entity level) rather than the denormalized
    # goal_level field, which may be null if entities were configured after import.
    active_levels = set(levels) if levels else {"org", "domain", "team"}

    def _level(goal: Goal) -> str | None:
        return goal.entity.level if goal.entity else None

    return {
        "org": [g for g in all_goals if _level(g) == "org" and "org" in active_levels],
        "domain": [g for g in all_goals if _level(g) == "domain" and "domain" in active_levels],
        "team": [g for g in all_goals if _level(g) == "team" and "team" in active_levels],
    }


def get_distinct_periods(db: Session) -> list[tuple[str, str]]:
    """Return all distinct (period, period_type) pairs from goals.

    Used to populate the period dropdown in the filter sidebar, with each pair
    carrying the type so the template can add data-type attributes for JS toggling.

    Returns:
        List of (period, period_type) tuples sorted by period string.
        Entries with null period or period_type are excluded.
    """
    rows = (
        db.query(Goal.period, Goal.period_type)
        .filter(Goal.period.isnot(None), Goal.period_type.isnot(None))
        .distinct()
        .order_by(Goal.period)
        .all()
    )
    return [(period, period_type) for period, period_type in rows]


def get_latest_confidence(db: Session, goal_id: int) -> GoalConfidence | None:
    """Return the most recent GoalConfidence for a goal, or None.

    "Latest" is determined by submitted_at descending, with id as tiebreaker
    for rows where submitted_at is null.
    """
    return (
        db.query(GoalConfidence)
        .filter(GoalConfidence.goal_id == goal_id)
        .order_by(
            GoalConfidence.submitted_at.desc().nullslast(),
            GoalConfidence.id.desc(),
        )
        .first()
    )


def compute_goal_stats(
    goals_by_level: dict[str, list[Goal]],
    confidences: dict[int, GoalConfidence | None],
) -> GoalStats:
    """Compute summary stats from the filtered goal set and pre-fetched confidences.

    Uses the already-fetched confidences dict to avoid additional DB queries.

    High confidence (Hoog Vertrouwen): latest score >= 7 (green traffic light).
    Needs attention (Aandacht nodig): latest score <= 3 (red traffic light).
    Goals without any confidence record are counted in total but neither stat bucket.

    Args:
        goals_by_level: Grouped goals from get_goals_filtered().
        confidences: Mapping of goal_id → GoalConfidence (or None) from the route.

    Returns:
        GoalStats with total, hoog_vertrouwen, and aandacht_nodig counts.
    """
    all_goals = goals_by_level["org"] + goals_by_level["domain"] + goals_by_level["team"]
    total = len(all_goals)
    hoog_vertrouwen = 0
    aandacht_nodig = 0

    for goal in all_goals:
        conf = confidences.get(goal.id)
        if conf is not None:
            if conf.confidence >= 7:
                hoog_vertrouwen += 1
            elif conf.confidence <= 3:
                aandacht_nodig += 1

    return GoalStats(
        total=total,
        hoog_vertrouwen=hoog_vertrouwen,
        aandacht_nodig=aandacht_nodig,
    )


@dataclass
class GoalNode:
    """A single node in the goal hierarchy tree.

    Attributes:
        goal: The Goal ORM object.
        confidence: Most recent GoalConfidence for this goal, or None.
        children: Child GoalNode objects (goals whose parent_goal_id == self.goal.id).
    """

    goal: Goal
    confidence: GoalConfidence | None
    children: "list[GoalNode]"


@dataclass
class DomainGroup:
    """A domain goal together with its direct team-level children.

    Used by the Strategiekaart template to render a domain column with
    its team cards below it.
    """

    domain_node: GoalNode
    team_nodes: list[GoalNode]


@dataclass
class OrgGroup:
    """An org goal together with its domain children and their teams.

    When an org goal has domain children in the current filter, they are
    collected here.  Org goals without domain children still appear as
    a standalone card (domain_groups is empty).
    """

    org_node: GoalNode
    domain_groups: list[DomainGroup]


def build_goal_tree(
    goals: list[Goal],
    confidences: dict[int, GoalConfidence | None],
) -> tuple[list[GoalNode], list[GoalNode]]:
    """Build a goal tree from a flat list of already-filtered goals.

    Organises goals by their parent_goal_id alignment relationship (not by
    organisational entity hierarchy).

    Rules:
      - Org-level goals with no parent_goal_id → tree roots.
      - Non-org goals with no parent_goal_id → unaligned section.
      - Goals whose parent_goal_id points to a goal NOT in the filtered set
        → unaligned section (parent filtered out; goal has no visible anchor).
      - All other goals → attached as children of their parent node.

    Children are sorted by confidence ascending so at-risk goals (low score)
    appear first. Goals with no confidence score sort after all scored goals.
    Within the same score, goals are sorted alphabetically by parsed_text.

    Args:
        goals: Flat list of Goal objects (already filtered by the route).
        confidences: Mapping goal_id → GoalConfidence (or None).

    Returns:
        Tuple of (roots, unaligned):
          roots     — GoalNode list ordered as received (caller determines sort).
          unaligned — non-org goals with no visible parent (either truly parentless
                      or whose parent was excluded by the active filter).
    """
    goal_ids = {g.id for g in goals}

    # Build a node for every goal upfront; children are populated below.
    nodes: dict[int, GoalNode] = {
        g.id: GoalNode(goal=g, confidence=confidences.get(g.id), children=[]) for g in goals
    }

    roots: list[GoalNode] = []
    unaligned: list[GoalNode] = []

    for g in goals:
        node = nodes[g.id]
        entity_level = g.entity.level if g.entity else None

        if g.parent_goal_id is None:
            # Org goals are always roots; other parentless goals are unaligned.
            if entity_level == "org":
                roots.append(node)
            else:
                unaligned.append(node)
        elif g.parent_goal_id not in goal_ids:
            # Parent exists but was excluded by the active filter (e.g. a quarterly
            # goal whose yearly parent is not shown).  Org and domain goals still
            # anchor a useful sub-tree, so promote them to roots.  Team goals have
            # no meaningful sub-tree of their own and go to the unaligned section.
            if entity_level in ("org", "domain"):
                roots.append(node)
            else:
                unaligned.append(node)
        else:
            # Has a parent in the current filtered set → attach as child.
            nodes[g.parent_goal_id].children.append(node)

    # Sort children: low confidence first (surfaces at-risk goals), None last,
    # with parsed_text as alphabetical tiebreaker.
    def _child_sort_key(n: GoalNode) -> tuple[int, str]:
        score = n.confidence.confidence if n.confidence else 11  # 11 > max score of 10
        return (score, n.goal.parsed_text or "")

    for node in nodes.values():
        if node.children:
            node.children.sort(key=_child_sort_key)

    return roots, unaligned


def build_map_groups(
    goals_by_level: dict[str, list[Goal]],
    confidences: dict[int, GoalConfidence | None],
) -> tuple[list[OrgGroup], list[DomainGroup], list[GoalNode]]:
    """Build the nested column-group structure for the Strategiekaart view.

    The Strategiekaart shows goals in three horizontal rows (org → domain →
    team), with CSS connector lines within each parent-group column.  This
    function organises the flat goal lists into that nested structure.

    Logic:
      - Org goals become OrgGroup roots.
      - Domain goals whose parent_goal_id points to an org goal in the current
        filter set → attached as children of that OrgGroup.
      - Domain goals with no org parent in the current set → free_domain_groups
        (rendered as standalone domain columns with their team children).
      - Team goals whose parent_goal_id points to a domain goal in the set →
        attached to that DomainGroup.
      - Team goals with no domain parent in the set → free_teams (rendered
        as standalone team cards without connector lines).

    Args:
        goals_by_level: Grouped goals from get_goals_filtered().
        confidences: Mapping goal_id → GoalConfidence (or None).

    Returns:
        Tuple of (org_groups, free_domain_groups, free_teams):
          org_groups         — OrgGroup list; each org goal + its domain/team tree.
          free_domain_groups — DomainGroup list; domain goals with no org parent
                              in the current filter + their team children.
          free_teams         — GoalNode list; team goals with no domain parent
                              in the current filter.
    """
    all_goals = goals_by_level["org"] + goals_by_level["domain"] + goals_by_level["team"]
    goal_ids = {g.id for g in all_goals}

    # Build a node for every goal.
    nodes: dict[int, GoalNode] = {
        g.id: GoalNode(goal=g, confidence=confidences.get(g.id), children=[]) for g in all_goals
    }

    # ── Group domain goals by their org parent ──
    # Only link a domain goal to an org parent if that parent actually appears
    # in the org bucket (entity.level == "org").  This keeps the function
    # correct even when entity levels are misconfigured in the DB.
    org_ids = {g.id for g in goals_by_level["org"]}
    domains_by_org_parent: dict[int, list[GoalNode]] = {}
    free_domain_nodes: list[GoalNode] = []

    for g in goals_by_level["domain"]:
        node = nodes[g.id]
        if g.parent_goal_id and g.parent_goal_id in org_ids:
            domains_by_org_parent.setdefault(g.parent_goal_id, []).append(node)
        else:
            free_domain_nodes.append(node)

    # ── Group team goals by their domain parent ──
    teams_by_domain_parent: dict[int, list[GoalNode]] = {}
    free_team_nodes: list[GoalNode] = []

    for g in goals_by_level["team"]:
        node = nodes[g.id]
        if g.parent_goal_id and g.parent_goal_id in goal_ids:
            teams_by_domain_parent.setdefault(g.parent_goal_id, []).append(node)
        else:
            free_team_nodes.append(node)

    # ── Build OrgGroups ──
    org_groups: list[OrgGroup] = []
    for g in goals_by_level["org"]:
        org_node = nodes[g.id]
        domain_groups = [
            DomainGroup(
                domain_node=domain_node,
                team_nodes=teams_by_domain_parent.get(domain_node.goal.id, []),
            )
            for domain_node in domains_by_org_parent.get(g.id, [])
        ]
        org_groups.append(OrgGroup(org_node=org_node, domain_groups=domain_groups))

    # ── Build free DomainGroups (domain goals not under any org goal) ──
    free_domain_groups: list[DomainGroup] = [
        DomainGroup(
            domain_node=domain_node,
            team_nodes=teams_by_domain_parent.get(domain_node.goal.id, []),
        )
        for domain_node in free_domain_nodes
    ]

    return org_groups, free_domain_groups, free_team_nodes
