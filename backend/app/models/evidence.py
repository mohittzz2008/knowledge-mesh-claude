"""Evidence Data Model for Permitted Developer Activity Ingestion."""

import uuid
from datetime import datetime
from typing import Optional, Any
from sqlalchemy import String, ForeignKey, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, utc_now


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    platform_connection_id: Mapped[str] = mapped_column(String(36), ForeignKey("platform_connections.id", ondelete="CASCADE"), nullable=False, index=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False) # 'problem_submission' | 'commit' | 'badge'
    raw_payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True) # Full source payload tracing
    normalized_payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True) # Standardized telemetry
    occurred_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="evidence_items")
    platform_connection: Mapped["PlatformConnection"] = relationship("PlatformConnection", back_populates="evidence_items")
