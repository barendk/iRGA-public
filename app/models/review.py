"""Review models — MonthlyReview, GoalConfidence, QuarterlyReview.

Monthly reviews are per-team (PPP fields + support request).
Confidence scores are per-goal (separate table).
Quarterly reviews are per-goal (score + reflection + recommendation).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.cycle import ReviewCycle
    from app.models.entity import StructuralEntity
    from app.models.goal import Goal


class MonthlyReview(Base):
    """Per-team monthly review with PPP fields and support request."""

    __tablename__ = "monthly_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Which team this review belongs to
    entity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("structural_entities.id"), nullable=False
    )
    # Which review cycle this belongs to
    cycle_id: Mapped[int] = mapped_column(Integer, ForeignKey("review_cycles.id"), nullable=False)

    # PPP fields (Progress, Problems, Plans)
    progress: Mapped[str | None] = mapped_column(Text, nullable=True)
    problems: Mapped[str | None] = mapped_column(Text, nullable=True)
    plans: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Team-level flag: needs help / flag for discussion
    support_request: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    submitted_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationships
    entity: Mapped[StructuralEntity] = relationship(
        "StructuralEntity", back_populates="monthly_reviews"
    )
    cycle: Mapped[ReviewCycle] = relationship("ReviewCycle", back_populates="monthly_reviews")

    def __repr__(self) -> str:
        return (
            f"<MonthlyReview(id={self.id}, entity_id={self.entity_id}, cycle_id={self.cycle_id})>"
        )


class GoalConfidence(Base):
    """Per-goal confidence score within a review cycle.

    Scale: 1-10 with traffic light mapping:
      1-3: red (at risk)
      4-6: orange (needs attention)
      7-10: green (on track)
    """

    __tablename__ = "goal_confidences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    goal_id: Mapped[int] = mapped_column(Integer, ForeignKey("goals.id"), nullable=False)
    cycle_id: Mapped[int] = mapped_column(Integer, ForeignKey("review_cycles.id"), nullable=False)
    # Confidence score: 1-10 (validated server-side)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    goal: Mapped[Goal] = relationship("Goal", back_populates="confidences")
    cycle: Mapped[ReviewCycle] = relationship("ReviewCycle", back_populates="goal_confidences")

    @property
    def traffic_light(self) -> str:
        """Return traffic light color based on confidence score."""
        if self.confidence <= 3:
            return "red"
        if self.confidence <= 6:
            return "orange"
        return "green"

    def __repr__(self) -> str:
        return f"<GoalConfidence(goal_id={self.goal_id}, confidence={self.confidence})>"


class QuarterlyReview(Base):
    """Per-goal quarterly review with score, reflection, and recommendation.

    Score: 1-5 based on KR achievement.
    Recommendation: finished, continue, change, or drop.
    """

    __tablename__ = "quarterly_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    goal_id: Mapped[int] = mapped_column(Integer, ForeignKey("goals.id"), nullable=False)
    period: Mapped[str] = mapped_column(String(10), nullable=False)
    # Score: 1-5 (validated server-side)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    reflection: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Recommendation: 'finished', 'continue', 'change', or 'drop'
    recommendation: Mapped[str | None] = mapped_column(String(20), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    submitted_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationships
    goal: Mapped[Goal] = relationship("Goal", back_populates="quarterly_reviews")

    def __repr__(self) -> str:
        return f"<QuarterlyReview(goal_id={self.goal_id}, score={self.score})>"
