"""Pydantic schemas for User & Unified Developer Intelligence Profile APIs."""

from typing import Optional, Any
from pydantic import BaseModel


class PlatformSummarySchema(BaseModel):
    platform: str
    connected: bool
    username: Optional[str] = None
    last_synced_at: Optional[str] = None


class SkillSummarySchema(BaseModel):
    skill_name: str
    slug: str
    category: str
    mastery: float
    status: str
    evidence_count: int
    sources: dict[str, int] = {}


class UserProfileResponse(BaseModel):
    user_id: str
    developer_name: str
    overall_skill_score: int
    total_evidence_count: int
    external_evidence_count: int = 0
    codelab_artifacts_count: int = 0
    code_artifacts_count: int = 0
    connected_platforms: list[PlatformSummarySchema] = []
    platform_counts: dict[str, int] = {}
    skills: list[SkillSummarySchema] = []
    next_best_action: Optional[dict[str, Any]] = None
