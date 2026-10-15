"""PlatformConnection Data Model."""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, utc_now


class PlatformConnection(Base):
    __tablename__ = "platform_connections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False) # 'LeetCode' | 'GitHub' | 'HackerRank'
    auth_type: Mapped[str] = mapped_column(String(32), nullable=False, default="username_public") # 'username_public' | 'oauth_token'
    username: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    auth_token_encrypted: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    connected: Mapped[bool] = mapped_column(Boolean, default=True)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="platform_connections")
    evidence_items: Mapped[list["Evidence"]] = relationship("Evidence", back_populates="platform_connection", cascade="all, delete-orphan")
