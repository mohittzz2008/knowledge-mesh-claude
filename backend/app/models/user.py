"""User and Developer Profile Data Models."""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, ForeignKey, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, utc_now


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    clerk_user_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    profile: Mapped[Optional["DeveloperProfile"]] = relationship("DeveloperProfile", back_populates="user", cascade="all, delete-orphan")
    platform_connections: Mapped[list["PlatformConnection"]] = relationship("PlatformConnection", back_populates="user", cascade="all, delete-orphan")
    evidence_items: Mapped[list["Evidence"]] = relationship("Evidence", back_populates="user", cascade="all, delete-orphan")
    skill_assessments: Mapped[list["SkillAssessment"]] = relationship("SkillAssessment", back_populates="user", cascade="all, delete-orphan")


class DeveloperProfile(Base):
    __tablename__ = "developer_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    primary_language: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    overall_skill_score: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    user: Mapped["User"] = relationship("User", back_populates="profile")
