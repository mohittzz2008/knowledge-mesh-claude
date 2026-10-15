"""Pydantic schemas for Evidence Ingestion and Querying."""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel


class EvidenceItemSchema(BaseModel):
    id: str
    user_id: str
    platform_connection_id: str
    external_id: Optional[str] = None
    title: str
    evidence_type: str  # 'commit' | 'repository' | 'activity' | 'code_file'
    raw_payload: Optional[dict[str, Any]] = None
    normalized_payload: Optional[dict[str, Any]] = None
    occurred_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class EvidenceListResponse(BaseModel):
    items: list[EvidenceItemSchema]
    total: int
    platform_counts: dict[str, int]
