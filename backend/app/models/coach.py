"""CoachConversation and CoachMessage Data Models."""

import uuid
from datetime import datetime
from typing import Optional, Any
from sqlalchemy import String, ForeignKey, Text, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, utc_now


class CoachConversation(Base):
    __tablename__ = "coach_conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), default="Knowledge Mesh Coaching Session", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    user: Mapped["User"] = relationship("User")
    messages: Mapped[list["CoachMessage"]] = relationship("CoachMessage", back_populates="conversation", cascade="all, delete-orphan")


class CoachMessage(Base):
    __tablename__ = "coach_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("coach_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    sender: Mapped[str] = mapped_column(String(32), default="ai", nullable=False) # 'user' | 'ai'
    content: Mapped[str] = mapped_column(Text, nullable=False)
    context_used: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    evidence_references: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    suggested_actions: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    # Relationships
    conversation: Mapped["CoachConversation"] = relationship("CoachConversation", back_populates="messages")
