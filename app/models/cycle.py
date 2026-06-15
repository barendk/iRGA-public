"""ReviewCycle model — tracks review periods (monthly, quarterly).

A cycle groups reviews together for a specific time period,
e.g. "January 2026 Monthly Check-in" or "2026 Q1 Quarterly Review".
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.review import GoalConfidence, MonthlyReview


class ReviewCycle(Base):
    __tablename__ = "review_cycles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Human-readable name, e.g. "Januari 2026" or "2026 Q1"
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Type: 'monthly' or 'quarterly'
    cycle_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # Period reference, e.g. "2026-01" (monthly) or "2026Q1" (quarterly)
    period: Mapped[str] = mapped_column(String(20), nullable=False)
    # Status: 'open' or 'closed'
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    monthly_reviews: Mapped[list[MonthlyReview]] = relationship(
        "MonthlyReview", back_populates="cycle"
    )
    goal_confidences: Mapped[list[GoalConfidence]] = relationship(
        "GoalConfidence", back_populates="cycle"
    )

    def __repr__(self) -> str:
        return (  # fmt: skip
            f"<ReviewCycle(id={self.id}, name='{self.name}', type='{self.cycle_type}')>"
        )
