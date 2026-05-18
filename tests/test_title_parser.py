"""Unit tests for the GitHub title parser.

Tests parse_title() and parse_period() with valid goals,
structural entities, edge cases, and invalid formats.
"""

from app.services.title_parser import parse_period, parse_title

# ── parse_period tests ──


class TestParsePeriod:
    def test_yearly_period(self) -> None:
        period, ptype = parse_period("2026")
        assert period == "2026"
        assert ptype == "yearly"

    def test_quarterly_period_uppercase(self) -> None:
        period, ptype = parse_period("2026Q1")
        assert period == "2026Q1"
        assert ptype == "quarterly"

    def test_quarterly_period_lowercase(self) -> None:
        """Period format is case-insensitive per CLAUDE.md."""
        period, ptype = parse_period("2026q3")
        assert period == "2026Q3"
        assert ptype == "quarterly"

    def test_all_valid_quarters(self) -> None:
        for q in range(1, 5):
            period, ptype = parse_period(f"2026Q{q}")
            assert period == f"2026Q{q}"
            assert ptype == "quarterly"

    def test_invalid_quarter_q5(self) -> None:
        """Only Q1-Q4 are valid quarters."""
        period, ptype = parse_period("2026Q5")
        assert period is None
        assert ptype is None

    def test_invalid_quarter_q0(self) -> None:
        period, ptype = parse_period("2026Q0")
        assert period is None
        assert ptype is None

    def test_invalid_format_text(self) -> None:
        period, ptype = parse_period("January")
        assert period is None
        assert ptype is None

    def test_invalid_format_partial_year(self) -> None:
        period, ptype = parse_period("202")
        assert period is None
        assert ptype is None

    def test_whitespace_handling(self) -> None:
        period, ptype = parse_period("  2026Q1  ")
        assert period == "2026Q1"
        assert ptype == "quarterly"


# ── parse_title tests ──


class TestParseTitleGoals:
    """Test parsing titles that represent goals (with period and goal text)."""

    def test_org_yearly_goal(self) -> None:
        result = parse_title("Acme Corp - 2026 - Become market leader in digital services")
        assert result.unit_name == "Acme Corp"
        assert result.period == "2026"
        assert result.period_type == "yearly"
        assert result.goal_text == "Become market leader in digital services"
        assert result.is_goal is True

    def test_domain_quarterly_goal(self) -> None:
        result = parse_title("Engineering - 2026Q1 - Reduce technical debt by 30%")
        assert result.unit_name == "Engineering"
        assert result.period == "2026Q1"
        assert result.period_type == "quarterly"
        assert result.goal_text == "Reduce technical debt by 30%"
        assert result.is_goal is True

    def test_team_quarterly_goal(self) -> None:
        result = parse_title("Team Alpha - 2026Q1 - Refactor authentication module")
        assert result.unit_name == "Team Alpha"
        assert result.period == "2026Q1"
        assert result.period_type == "quarterly"
        assert result.goal_text == "Refactor authentication module"
        assert result.is_goal is True

    def test_goal_text_with_dashes(self) -> None:
        """Goal text can contain dashes (max 2 splits on ' - ')."""
        result = parse_title("Team Beta - 2026Q1 - Set up CI/CD - including rollback procedures")
        assert result.unit_name == "Team Beta"
        assert result.period == "2026Q1"
        assert result.goal_text == "Set up CI/CD - including rollback procedures"
        assert result.is_goal is True

    def test_case_insensitive_period(self) -> None:
        result = parse_title("Engineering - 2026q2 - Cloud migration")
        assert result.period == "2026Q2"
        assert result.period_type == "quarterly"
        assert result.is_goal is True


class TestParseTitleEntities:
    """Test parsing titles that represent structural entities (no period)."""

    def test_simple_entity(self) -> None:
        result = parse_title("Engineering")
        assert result.unit_name == "Engineering"
        assert result.period is None
        assert result.period_type is None
        assert result.goal_text is None
        assert result.is_goal is False

    def test_entity_with_space(self) -> None:
        result = parse_title("Team Alpha")
        assert result.unit_name == "Team Alpha"
        assert result.is_goal is False

    def test_entity_single_word(self) -> None:
        result = parse_title("Acme Corp")
        assert result.unit_name == "Acme Corp"
        assert result.is_goal is False


class TestParseTitleEdgeCases:
    """Test edge cases and invalid formats."""

    def test_empty_title(self) -> None:
        result = parse_title("")
        assert result.unit_name == ""
        assert result.is_goal is False

    def test_whitespace_only(self) -> None:
        result = parse_title("   ")
        assert result.unit_name == ""
        assert result.is_goal is False

    def test_leading_trailing_whitespace(self) -> None:
        result = parse_title("  Team Alpha - 2026Q1 - Some goal  ")
        assert result.unit_name == "Team Alpha"
        assert result.goal_text == "Some goal"

    def test_invalid_period_three_parts(self) -> None:
        """Three parts but invalid period — treated as entity."""
        result = parse_title("Team Alpha - January - Some goal")
        assert result.unit_name == "Team Alpha - January - Some goal"
        assert result.is_goal is False

    def test_two_parts_with_valid_period(self) -> None:
        """Two parts where second is a valid period but no goal text."""
        result = parse_title("Engineering - 2026Q1")
        assert result.unit_name == "Engineering"
        assert result.period == "2026Q1"
        assert result.goal_text is None
        assert result.is_goal is False

    def test_two_parts_invalid_period(self) -> None:
        """Two parts where second is NOT a valid period."""
        result = parse_title("Team Alpha - Something")
        assert result.unit_name == "Team Alpha - Something"
        assert result.is_goal is False
