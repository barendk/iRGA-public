"""Unit tests for goal_service.build_goal_tree.

Uses lightweight SimpleNamespace stubs instead of real ORM objects so these
tests run without a database connection.
"""

from types import SimpleNamespace
from typing import Any

from app.services.goal_service import GoalNode, build_goal_tree, build_map_groups

# ── Helpers ─────────────────────────────────────────────────────────────────


def _goal(
    id: int,
    parent_goal_id: int | None = None,
    entity_level: str = "team",
    parsed_text: str = "Goal",
) -> Any:
    """Minimal Goal-like stub for tree tests."""
    entity = SimpleNamespace(level=entity_level)
    return SimpleNamespace(
        id=id, parent_goal_id=parent_goal_id, entity=entity, parsed_text=parsed_text
    )


def _conf(score: int) -> Any:
    """Minimal GoalConfidence-like stub."""
    return SimpleNamespace(confidence=score)


def _ids(nodes: list[GoalNode]) -> list[int]:
    return [n.goal.id for n in nodes]


# ── Classification tests ─────────────────────────────────────────────────────


class TestBuildGoalTreeClassification:
    """Goals are correctly classified into roots, children, or unaligned."""

    def test_empty_input(self) -> None:
        roots, unaligned = build_goal_tree([], {})
        assert roots == []
        assert unaligned == []

    def test_org_goal_without_parent_is_root(self) -> None:
        goals = [_goal(1, entity_level="org")]
        roots, unaligned = build_goal_tree(goals, {})
        assert _ids(roots) == [1]
        assert unaligned == []

    def test_team_goal_without_parent_is_unaligned(self) -> None:
        goals = [_goal(1, entity_level="team")]
        roots, unaligned = build_goal_tree(goals, {})
        assert roots == []
        assert _ids(unaligned) == [1]

    def test_domain_goal_without_parent_is_unaligned(self) -> None:
        goals = [_goal(1, entity_level="domain")]
        roots, unaligned = build_goal_tree(goals, {})
        assert roots == []
        assert _ids(unaligned) == [1]

    def test_child_attached_to_parent_node(self) -> None:
        goals = [
            _goal(1, entity_level="org"),
            _goal(2, parent_goal_id=1, entity_level="team"),
        ]
        roots, unaligned = build_goal_tree(goals, {})
        assert _ids(roots) == [1]
        assert _ids(roots[0].children) == [2]
        assert unaligned == []

    def test_goal_with_filtered_out_parent_goes_to_unaligned(self) -> None:
        """Parent exists in the DB but was excluded by the active filter.

        The goal should appear in the unaligned section rather than being
        promoted to a root, since it is not semantically a top-level goal.
        """
        goals = [_goal(2, parent_goal_id=99, entity_level="team")]  # 99 not in list
        roots, unaligned = build_goal_tree(goals, {})
        assert roots == []
        assert _ids(unaligned) == [2]

    def test_multiple_roots(self) -> None:
        goals = [
            _goal(1, entity_level="org", parsed_text="A"),
            _goal(2, entity_level="org", parsed_text="B"),
        ]
        roots, unaligned = build_goal_tree(goals, {})
        assert len(roots) == 2
        assert unaligned == []

    def test_three_level_hierarchy(self) -> None:
        goals = [
            _goal(1, entity_level="org"),
            _goal(2, parent_goal_id=1, entity_level="domain"),
            _goal(3, parent_goal_id=2, entity_level="team"),
        ]
        roots, unaligned = build_goal_tree(goals, {})
        assert _ids(roots) == [1]
        assert _ids(roots[0].children) == [2]
        assert _ids(roots[0].children[0].children) == [3]
        assert unaligned == []

    def test_mixed_parentless_goals(self) -> None:
        """Org goals → roots; non-org parentless → unaligned; children → children."""
        goals = [
            _goal(1, entity_level="org"),
            _goal(2, entity_level="team"),  # parentless team → unaligned
            _goal(3, parent_goal_id=1, entity_level="domain"),  # child of 1
        ]
        roots, unaligned = build_goal_tree(goals, {})
        assert _ids(roots) == [1]
        assert _ids(roots[0].children) == [3]
        assert _ids(unaligned) == [2]


# ── Confidence attachment ────────────────────────────────────────────────────


class TestBuildGoalTreeConfidence:
    """Confidence records are correctly attached to nodes."""

    def test_confidence_attached(self) -> None:
        goals = [_goal(1, entity_level="org")]
        conf = _conf(8)
        roots, _ = build_goal_tree(goals, {1: conf})
        assert roots[0].confidence is conf

    def test_missing_confidence_is_none(self) -> None:
        goals = [_goal(1, entity_level="org")]
        roots, _ = build_goal_tree(goals, {})
        assert roots[0].confidence is None


# ── Child sort order ─────────────────────────────────────────────────────────


class TestBuildGoalTreeChildSorting:
    """Children are sorted by confidence ascending (low/at-risk first), None last."""

    def test_children_sorted_low_confidence_first(self) -> None:
        goals = [
            _goal(1, entity_level="org"),
            _goal(2, parent_goal_id=1, entity_level="team", parsed_text="B"),
            _goal(3, parent_goal_id=1, entity_level="team", parsed_text="A"),
            _goal(4, parent_goal_id=1, entity_level="team", parsed_text="C"),
        ]
        confidences = {2: _conf(7), 3: _conf(2), 4: _conf(5)}
        roots, _ = build_goal_tree(goals, confidences)
        child_scores = [c.confidence.confidence for c in roots[0].children]  # type: ignore[union-attr]
        assert child_scores == [2, 5, 7]

    def test_no_confidence_sorts_after_scored_goals(self) -> None:
        goals = [
            _goal(1, entity_level="org"),
            _goal(2, parent_goal_id=1, entity_level="team", parsed_text="A"),  # score 3
            _goal(3, parent_goal_id=1, entity_level="team", parsed_text="B"),  # no score
        ]
        roots, _ = build_goal_tree(goals, {2: _conf(3)})
        children = roots[0].children
        assert children[0].goal.id == 2  # score 3 comes first
        assert children[1].goal.id == 3  # None comes last

    def test_equal_scores_tiebreak_by_parsed_text(self) -> None:
        goals = [
            _goal(1, entity_level="org"),
            _goal(2, parent_goal_id=1, entity_level="team", parsed_text="Zebra"),
            _goal(3, parent_goal_id=1, entity_level="team", parsed_text="Alpha"),
        ]
        confidences = {2: _conf(5), 3: _conf(5)}
        roots, _ = build_goal_tree(goals, confidences)
        children = roots[0].children
        assert children[0].goal.parsed_text == "Alpha"
        assert children[1].goal.parsed_text == "Zebra"

    def test_multiple_none_scores_tiebreak_by_parsed_text(self) -> None:
        goals = [
            _goal(1, entity_level="org"),
            _goal(2, parent_goal_id=1, entity_level="team", parsed_text="Zebra"),
            _goal(3, parent_goal_id=1, entity_level="team", parsed_text="Alpha"),
        ]
        roots, _ = build_goal_tree(goals, {})  # no confidences at all
        children = roots[0].children
        assert children[0].goal.parsed_text == "Alpha"
        assert children[1].goal.parsed_text == "Zebra"

    def test_sort_applies_at_every_level(self) -> None:
        """Sorting is applied to children lists at all depths, not just root level."""
        goals = [
            _goal(1, entity_level="org"),
            _goal(2, parent_goal_id=1, entity_level="domain"),
            _goal(3, parent_goal_id=2, entity_level="team", parsed_text="Z"),
            _goal(4, parent_goal_id=2, entity_level="team", parsed_text="A"),
        ]
        confidences = {3: _conf(8), 4: _conf(2)}
        roots, _ = build_goal_tree(goals, confidences)
        grandchildren = roots[0].children[0].children
        assert grandchildren[0].goal.id == 4  # score 2
        assert grandchildren[1].goal.id == 3  # score 8


# ── build_map_groups ─────────────────────────────────────────────────────────


def _gbl(
    org: list | None = None,
    domain: list | None = None,
    team: list | None = None,
) -> dict:
    """Build a goals_by_level dict from optional per-level lists."""
    return {"org": org or [], "domain": domain or [], "team": team or []}


class TestBuildMapGroups:
    """build_map_groups() correctly assembles the Strategiekaart column structure."""

    def test_empty_input(self) -> None:
        org_groups, free_domains, free_teams = build_map_groups(_gbl(), {})
        assert org_groups == []
        assert free_domains == []
        assert free_teams == []

    def test_org_only_no_children(self) -> None:
        """An org goal with no domain children yields one OrgGroup with empty domain_groups."""
        org_groups, free_domains, free_teams = build_map_groups(
            _gbl(org=[_goal(1, entity_level="org")]), {}
        )
        assert len(org_groups) == 1
        assert org_groups[0].org_node.goal.id == 1
        assert org_groups[0].domain_groups == []
        assert free_domains == []
        assert free_teams == []

    def test_connected_org_domain_team(self) -> None:
        """Fully connected org→domain→team hierarchy ends up in a single OrgGroup."""
        org_groups, free_domains, free_teams = build_map_groups(
            _gbl(
                org=[_goal(1, entity_level="org")],
                domain=[_goal(2, parent_goal_id=1, entity_level="domain")],
                team=[_goal(3, parent_goal_id=2, entity_level="team")],
            ),
            {},
        )
        assert len(org_groups) == 1
        assert free_domains == []
        assert free_teams == []
        dg = org_groups[0].domain_groups[0]
        assert dg.domain_node.goal.id == 2
        assert len(dg.team_nodes) == 1
        assert dg.team_nodes[0].goal.id == 3

    def test_free_domain_parent_absent_from_filter(self) -> None:
        """Domain goal whose parent is not in the current filter goes to free_domain_groups."""
        org_groups, free_domains, free_teams = build_map_groups(
            _gbl(domain=[_goal(2, parent_goal_id=99, entity_level="domain")]),
            {},
        )
        assert org_groups == []
        assert len(free_domains) == 1
        assert free_domains[0].domain_node.goal.id == 2
        assert free_teams == []

    def test_free_domain_no_parent_at_all(self) -> None:
        """Domain goal with no parent_goal_id goes to free_domain_groups."""
        org_groups, free_domains, free_teams = build_map_groups(
            _gbl(domain=[_goal(2, entity_level="domain")]),
            {},
        )
        assert len(free_domains) == 1
        assert free_domains[0].domain_node.goal.id == 2

    def test_free_team_no_parent(self) -> None:
        """Team goal with no parent in the current filter set goes to free_teams."""
        org_groups, free_domains, free_teams = build_map_groups(
            _gbl(team=[_goal(3, entity_level="team")]),
            {},
        )
        assert org_groups == []
        assert free_domains == []
        assert len(free_teams) == 1
        assert free_teams[0].goal.id == 3

    def test_misconfigured_domain_claiming_domain_parent(self) -> None:
        """Domain goal whose parent is another domain goal (not an org goal)
        must not be attached to an OrgGroup. build_map_groups uses org_ids
        (bucket membership), not entity.level, so a misconfigured parent
        cannot cause a spurious org linkage.
        """
        org_groups, free_domains, free_teams = build_map_groups(
            _gbl(
                domain=[
                    _goal(1, entity_level="domain"),
                    _goal(2, parent_goal_id=1, entity_level="domain"),
                ]
            ),
            {},
        )
        assert org_groups == []
        # Both domain goals end up as free domain groups (neither links to an org parent).
        assert len(free_domains) == 2

    def test_confidence_attached_to_all_levels(self) -> None:
        """Confidence records are correctly wired to org, domain, and team nodes."""
        conf_org, conf_domain, conf_team = _conf(8), _conf(5), _conf(2)
        org_groups, _, _ = build_map_groups(
            _gbl(
                org=[_goal(1, entity_level="org")],
                domain=[_goal(2, parent_goal_id=1, entity_level="domain")],
                team=[_goal(3, parent_goal_id=2, entity_level="team")],
            ),
            {1: conf_org, 2: conf_domain, 3: conf_team},
        )
        assert org_groups[0].org_node.confidence is conf_org
        dg = org_groups[0].domain_groups[0]
        assert dg.domain_node.confidence is conf_domain
        assert dg.team_nodes[0].confidence is conf_team

    def test_multiple_domains_under_one_org(self) -> None:
        """Multiple domain children are all attached to their shared org parent."""
        org_groups, free_domains, free_teams = build_map_groups(
            _gbl(
                org=[_goal(1, entity_level="org")],
                domain=[
                    _goal(2, parent_goal_id=1, entity_level="domain"),
                    _goal(3, parent_goal_id=1, entity_level="domain"),
                ],
            ),
            {},
        )
        assert len(org_groups) == 1
        assert len(org_groups[0].domain_groups) == 2
        assert free_domains == []
