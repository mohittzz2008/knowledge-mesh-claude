"""Problem, ProblemRecommendation, and CodeAttempt Data Models."""

import uuid
from datetime import datetime
from typing import Optional, Any
from sqlalchemy import String, ForeignKey, Text, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, utc_now


class Problem(Base):
    __tablename__ = "problems"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    platform: Mapped[str] = mapped_column(String(32), default="GitHub", nullable=False)
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    difficulty: Mapped[str] = mapped_column(String(32), default="Easy", nullable=False) # 'Easy' | 'Medium' | 'Hard'
    topics: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    language: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(64), default="Permitted Platform Reference", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ProblemRecommendation(Base):
    __tablename__ = "problem_recommendations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    problem_id: Mapped[str] = mapped_column(String(36), ForeignKey("problems.id", ondelete="CASCADE"), nullable=False, index=True)
    target_skill_slug: Mapped[str] = mapped_column(String(128), nullable=False)
    prerequisite_skill_slug: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    recommendation_reason: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_strength: Mapped[str] = mapped_column(String(32), default="Limited", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False) # 'active' | 'completed' | 'dismissed'
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    # Relationships
    user: Mapped["User"] = relationship("User")
    problem: Mapped["Problem"] = relationship("Problem")


class CodeAttempt(Base):
    __tablename__ = "code_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    problem_id: Mapped[str] = mapped_column(String(36), ForeignKey("problems.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="attempted", nullable=False) # 'attempted' | 'completed' | 'failed'
    source_platform: Mapped[str] = mapped_column(String(32), default="GitHub", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    # Relationships
    user: Mapped["User"] = relationship("User")
    problem: Mapped["Problem"] = relationship("Problem")
