"""StructuralEntity model — organizational units (org, domain, team).

Represents the three-level hierarchy: org -> domain -> team.
Entity levels are assigned via the admin UI after TSV import.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.goal import Goal
    from app.models.review import MonthlyReview


class StructuralEntity(Base):
    __tablename__ = "structural_entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    # Level: 'org', 'domain', or 'team' — set via admin UI
    level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Parent entity (e.g. team -> domain, domain -> org)
    parent_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("structural_entities.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    parent: Mapped[StructuralEntity | None] = relationship(
        "StructuralEntity", remote_side=[id], back_populates="children"
    )
    children: Mapped[list[StructuralEntity]] = relationship(
        "StructuralEntity", back_populates="parent"
    )
    goals: Mapped[list[Goal]] = relationship("Goal", back_populates="entity")
    monthly_reviews: Mapped[list[MonthlyReview]] = relationship(
        "MonthlyReview", back_populates="entity"
    )

    def __repr__(self) -> str:
        return f"<StructuralEntity(id={self.id}, name='{self.name}', level='{self.level}')>"
