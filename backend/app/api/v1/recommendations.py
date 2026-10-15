"""FastAPI Router for Recommendations, Next Best Action, and Learning Path APIs."""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.api.v1.auth import get_current_user
from app.schemas.recommendation import (
    NextBestActionResponse,
    PracticeRecommendationSchema,
    PracticeRecommendationListResponse,
    LearningPathResponse,
)
from app.services.recommendations.recommendation_service import RecommendationService

router = APIRouter(tags=["Recommendations & Learning Path"])


@router.get("/next-best-action", response_model=NextBestActionResponse)
def get_next_best_action(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve user's current Next Best Action with explicit evidence justification."""
    service = RecommendationService()
    nba_data = service.get_next_best_action(current_user.id, db)
    return NextBestActionResponse.model_validate(nba_data)


@router.get("/recommendations", response_model=PracticeRecommendationListResponse)
def get_practice_recommendations(
    skill: str = Query("recursion", description="Target skill slug (or 'all')"),
    platform: Optional[str] = Query(None, description="Filter by platform (e.g. 'GitHub', 'LeetCode')"),
    difficulty: Optional[str] = Query(None, description="Filter by difficulty ('Easy', 'Medium', 'Hard')"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve ranked practice recommendations for a target skill for current user."""
    service = RecommendationService()
    recs = service.get_practice_recommendations(current_user.id, db, target_skill_slug=skill, limit=10)

    if platform:
        recs = [r for r in recs if r["platform"].lower() == platform.lower()]

    if difficulty:
        recs = [r for r in recs if r["difficulty"].lower() == difficulty.lower()]

    items = [PracticeRecommendationSchema.model_validate(r) for r in recs]
    return PracticeRecommendationListResponse(recommendations=items, total=len(items))


@router.get("/learning-path", response_model=LearningPathResponse)
def get_personalized_learning_path(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve dynamic personalized learning path roadmap generated from Knowledge Mesh telemetry."""
    service = RecommendationService()
    path_data = service.get_learning_path(current_user.id, db)
    return LearningPathResponse.model_validate(path_data)
