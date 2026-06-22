"""Integration tests for the TSV import service.

Tests the two-pass import algorithm, parent linking,
idempotent re-imports, and validation error handling.
"""

from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.models.entity import StructuralEntity
from app.models.goal import Goal
from app.services.import_service import import_goals_from_tsv


@pytest.fixture()
def write_tsv(tmp_path: Path):
    """Factory fixture to write TSV content to a temp file."""

    def _write(content: str) -> Path:
        tsv_path = tmp_path / "test.tsv"
        tsv_path.write_text(content, encoding="utf-8")
        return tsv_path

    return _write


TSV_HEADER = "Title\tURL\tAssignees\tStatus\tSub-issues progress\tParent issue\tStart Date\n"

SAMPLE_TSV = TSV_HEADER + (
    "Acme Corp - 2026 - Top goal\t"
    "https://github.com/org/repo/issues/1\t\t"
    "In Progress\t\t\tJan 1, 2026\n"
    "Engineering\t"
    "https://github.com/org/repo/issues/10\t\t"
    "In Progress\t\t\tJan 1, 2026\n"
    "Engineering - 2026Q1 - Quarterly goal\t"
    "https://github.com/org/repo/issues/11\tbob\t"
    "Todo\t\t"
    "https://github.com/org/repo/issues/1\t"
    "Jan 1, 2026\n"
    "Team Alpha\t"
    "https://github.com/org/repo/issues/100\t\t"
    "In Progress\t\t\tJan 1, 2026\n"
    "Team Alpha - 2026Q1 - Team goal\t"
    "https://github.com/org/repo/issues/101\t"
    "alice\tIn Progress\t\t"
    "https://github.com/org/repo/issues/11\t"
    "Jan 1, 2026\n"
)


class TestImportBasic:
    """Test basic import functionality."""

    def test_creates_entities_and_goals(self, db: Session, write_tsv) -> None:
        tsv_path = write_tsv(SAMPLE_TSV)
        result = import_goals_from_tsv(db, tsv_path)

        assert result.entities_created == 3  # Acme Corp, Engineering, Team Alpha
        assert result.entities_seen == 5  # Each row references an entity
        assert result.goals_created == 3  # Top goal, Quarterly goal, Team goal
        assert result.parent_links_set == 2

    def test_entity_names_correct(self, db: Session, write_tsv) -> None:
        tsv_path = write_tsv(SAMPLE_TSV)
        import_goals_from_tsv(db, tsv_path)

        names = {e.name for e in db.query(StructuralEntity).all()}
        assert names == {"Acme Corp", "Engineering", "Team Alpha"}

    def test_goal_fields_populated(self, db: Session, write_tsv) -> None:
        tsv_path = write_tsv(SAMPLE_TSV)
        import_goals_from_tsv(db, tsv_path)

        goal = (
            db.query(Goal).filter(Goal.github_url == "https://github.com/org/repo/issues/101").one()
        )
        assert goal.title == "Team Alpha - 2026Q1 - Team goal"
        assert goal.parsed_text == "Team goal"
        assert goal.owner == "alice"
        assert goal.period == "2026Q1"
        assert goal.period_type == "quarterly"
        assert goal.status == "In Progress"
        assert goal.github_issue_id == 101

    def test_parent_linking(self, db: Session, write_tsv) -> None:
        """Pass 2 should link child goals to parent goals via GitHub URLs."""
        tsv_path = write_tsv(SAMPLE_TSV)
        import_goals_from_tsv(db, tsv_path)

        team_goal = (
            db.query(Goal).filter(Goal.github_url == "https://github.com/org/repo/issues/101").one()
        )
        parent_goal = (
            db.query(Goal).filter(Goal.github_url == "https://github.com/org/repo/issues/11").one()
        )
        assert team_goal.parent_goal_id == parent_goal.id


class TestImportIdempotent:
    """Test that re-importing the same TSV is idempotent."""

    def test_reimport_updates_not_duplicates(self, db: Session, write_tsv) -> None:
        tsv_path = write_tsv(SAMPLE_TSV)

        result1 = import_goals_from_tsv(db, tsv_path)
        assert result1.goals_created == 3

        result2 = import_goals_from_tsv(db, tsv_path)
        assert result2.goals_created == 0
        assert result2.goals_updated == 3

        # Should still have exactly 3 goals
        assert db.query(Goal).count() == 3


class TestImportEdgeCases:
    """Test import with edge cases and validation."""

    def test_empty_title_skipped(self, db: Session, write_tsv) -> None:
        tsv = TSV_HEADER + "\t\t\t\t\t\t\n"
        tsv_path = write_tsv(tsv)
        result = import_goals_from_tsv(db, tsv_path)
        assert result.entities_created == 0
        assert result.goals_created == 0
        assert len(result.warnings) == 1

    def test_missing_parent_warns(self, db: Session, write_tsv) -> None:
        tsv = TSV_HEADER + (
            "Team - 2026Q1 - Goal\t"
            "https://github.com/org/repo/issues/1\t\t"
            "Todo\t\t"
            "https://github.com/org/repo/issues/999\t\n"
        )
        tsv_path = write_tsv(tsv)
        result = import_goals_from_tsv(db, tsv_path)
        assert result.goals_created == 1
        assert result.parent_links_set == 0
        # Should warn about missing parent
        assert any("niet gevonden" in w for w in result.warnings)

    def test_sample_goals_file(self, db: Session) -> None:
        """Test with the actual sample_goals.tsv file."""
        sample_path = Path("test data/sample_goals.tsv")
        if not sample_path.exists():
            pytest.skip("sample_goals.tsv not found")

        result = import_goals_from_tsv(db, sample_path)
        assert result.entities_created == 5
        assert result.goals_created == 10  # includes quarterly org goal added in Step 9
        assert result.parent_links_set == 9  # +1 for the new org quarterly goal
        assert len(result.warnings) == 0
