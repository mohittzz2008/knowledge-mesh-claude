"""CodeArtifact and CodeAnalysis Data Models."""

import uuid
from datetime import datetime
from typing import Optional, Any
from sqlalchemy import String, Integer, Boolean, ForeignKey, Text, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, utc_now


class CodeArtifact(Base):
    __tablename__ = "code_artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    platform_connection_id: Mapped[str] = mapped_column(String(36), ForeignKey("platform_connections.id", ondelete="CASCADE"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(32), default="GitHub", nullable=False)
    repository: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    commit_sha: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    language: Mapped[str] = mapped_column(String(64), nullable=False)
    code_content: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    # Relationships
    user: Mapped["User"] = relationship("User")
    platform_connection: Mapped["PlatformConnection"] = relationship("PlatformConnection")
    analysis: Mapped[Optional["CodeAnalysis"]] = relationship("CodeAnalysis", back_populates="code_artifact", uselist=False, cascade="all, delete-orphan")


class CodeAnalysis(Base):
    __tablename__ = "code_analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code_artifact_id: Mapped[str] = mapped_column(String(36), ForeignKey("code_artifacts.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(64), nullable=False)
    lines_of_code: Mapped[int] = mapped_column(Integer, default=0)
    function_count: Mapped[int] = mapped_column(Integer, default=0)
    class_count: Mapped[int] = mapped_column(Integer, default=0)
    cyclomatic_complexity: Mapped[int] = mapped_column(Integer, default=1)
    has_recursion: Mapped[bool] = mapped_column(Boolean, default=False)
    detected_concepts: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    data_structures: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    analysis_summary: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    # Relationships
    code_artifact: Mapped["CodeArtifact"] = relationship("CodeArtifact", back_populates="analysis")
