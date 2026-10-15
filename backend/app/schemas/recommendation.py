"""Pydantic schemas for Recommendation and Learning Path APIs."""

from typing import Optional, Any
from pydantic import BaseModel


class NextBestActionResponse(BaseModel):
    target_skill: str
    slug: str
    reason: str
    evidence_count: int
    recommended_difficulty: str
    learning_objective: str
    prerequisites: list[str] = []
    has_sufficient_evidence: bool = True


class PracticeRecommendationSchema(BaseModel):
    problem_id: str
    platform: str
    title: str
    url: Optional[str] = None
    difficulty: str
    topics: list[str] = []
    target_skill_slug: str
    reason: str
    source: str
    status_label: str
    is_real_data: bool


class PracticeRecommendationListResponse(BaseModel):
    recommendations: list[PracticeRecommendationSchema]
    total: int


class LearningPathStepSchema(BaseModel):
    id: str
    step_number: int
    title: str
    slug: str
    category: str
    status: str # 'completed' | 'in_progress' | 'recommended' | 'locked'
    mastery: int
    evidence_count: int
    why: str
    prerequisites: list[str] = []
    recommended_practice: str


class LearningPathResponse(BaseModel):
    user_id: str
    target_goal: str
    current_focus_skill: str
    steps: list[LearningPathStepSchema]
    total_steps: int
