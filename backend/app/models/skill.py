"""Skill, SkillRelationship, and SkillAssessment Data Models."""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Float, ForeignKey, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, Session
from app.models.base import Base, utc_now


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False) # 'core' | 'advanced' | 'gap'
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    assessments: Mapped[list["SkillAssessment"]] = relationship("SkillAssessment", back_populates="skill")


class SkillRelationship(Base):
    __tablename__ = "skill_relationships"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    parent_skill_id: Mapped[str] = mapped_column(String(36), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False)
    child_skill_id: Mapped[str] = mapped_column(String(36), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(64), default="prerequisite") # 'prerequisite' | 'subskill'


class SkillAssessment(Base):
    __tablename__ = "skill_assessments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    skill_id: Mapped[str] = mapped_column(String(36), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True)
    mastery_score: Mapped[float] = mapped_column(Float, default=0.0) # 0.0 to 100.0
    status: Mapped[str] = mapped_column(String(32), default="developing") # 'mastered' | 'developing' | 'weak'
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="skill_assessments")
    skill: Mapped["Skill"] = relationship("Skill", back_populates="assessments")


def get_latest_user_assessments(db: "Session", user_id: str) -> dict[str, SkillAssessment]:
    """Retrieve the latest SkillAssessment per skill for a given user.

    Sorts by evaluated_at DESC, id DESC to break any ties deterministically.
    Returns a mapping of skill_id -> latest SkillAssessment.
    """
    assessments = (
        db.query(SkillAssessment)
        .filter(SkillAssessment.user_id == user_id)
        .order_by(SkillAssessment.evaluated_at.desc(), SkillAssessment.id.desc())
        .all()
    )
    latest_by_skill_id: dict[str, SkillAssessment] = {}
    for a in assessments:
        if a.skill_id not in latest_by_skill_id:
            latest_by_skill_id[a.skill_id] = a
    return latest_by_skill_id

