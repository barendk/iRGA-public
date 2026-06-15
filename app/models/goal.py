"""Goal model — individual goals parsed from GitHub Projects TSV export.

Goals follow the title format: "<unit> - <period> - <goal text>"
Two relationship types:
  - entity_id: organizational ownership (which team/domain owns this)
  - parent_goal_id: goal alignment (which goal this contributes to)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.entity import StructuralEntity
    from app.models.review import GoalConfidence, QuarterlyReview


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # GitHub metadata
    github_issue_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    github_url: Mapped[str | None] = mapped_column(String(500), unique=True, nullable=True)

    # Parsed from title: "<unit> - <period> - <goal text>"
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    parsed_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Owner (GitHub assignee)
    owner: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Period: "2026" (yearly) or "2026Q1" (quarterly)
    period: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # Period type: 'yearly' or 'quarterly'
    period_type: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # GitHub issue status (e.g. "In Progress", "Todo", "Done")
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Organizational ownership — which entity owns this goal
    entity_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("structural_entities.id"), nullable=True
    )

    # Goal alignment — which higher-level goal this contributes to
    parent_goal_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("goals.id"), nullable=True
    )

    # Denormalized level for query convenience (org, domain, team)
    goal_level: Mapped[str | None] = mapped_column(String(20), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    entity: Mapped[StructuralEntity | None] = relationship(
        "StructuralEntity", back_populates="goals"
    )
    parent_goal: Mapped[Goal | None] = relationship(
        "Goal", remote_side=[id], back_populates="child_goals"
    )
    child_goals: Mapped[list[Goal]] = relationship("Goal", back_populates="parent_goal")
    confidences: Mapped[list[GoalConfidence]] = relationship(
        "GoalConfidence", back_populates="goal"
    )
    quarterly_reviews: Mapped[list[QuarterlyReview]] = relationship(
        "QuarterlyReview", back_populates="goal"
    )

    def __repr__(self) -> str:
        return f"<Goal(id={self.id}, title='{self.title[:40]}...')>"
