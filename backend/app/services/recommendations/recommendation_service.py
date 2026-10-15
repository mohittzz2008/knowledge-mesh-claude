"""Recommendation Service Orchestrator."""

from typing import Any
from sqlalchemy.orm import Session
from app.services.recommendations.gap_engine import KnowledgeGapEngine
from app.services.recommendations.next_best_action import NextBestActionService
from app.services.recommendations.problem_matcher import ProblemMatcherService
from app.services.recommendations.learning_path_generator import LearningPathGenerator


class RecommendationService:
    """Orchestrates Next Best Action, problem recommendations, and dynamic learning paths."""

    def get_next_best_action(self, user_id: str, db: Session) -> dict[str, Any]:
        nba_service = NextBestActionService()
        return nba_service.determine_next_best_action(user_id, db)

    def get_practice_recommendations(
        self, user_id: str, db: Session, target_skill_slug: str = "recursion", limit: int = 5
    ) -> list[dict[str, Any]]:
        matcher = ProblemMatcherService()
        return matcher.get_ranked_recommendations(user_id, target_skill_slug, db, limit=limit)

    def get_learning_path(self, user_id: str, db: Session) -> dict[str, Any]:
        generator = LearningPathGenerator()
        return generator.generate_roadmap(user_id, db)
