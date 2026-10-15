"""Coach Context Builder Service."""

from typing import Any
from sqlalchemy.orm import Session
from app.models.user import User, DeveloperProfile
from app.models.platform import PlatformConnection
from app.models.evidence import Evidence
from app.models.code_artifact import CodeArtifact
from app.services.recommendations.recommendation_service import RecommendationService
from app.services.mesh.graph_builder import KnowledgeMeshGraphBuilder
from app.services.coach.mistake_detector import MistakeDetectorEngine
from app.services.coach.question_router import QuestionRouter, IntentType


class CoachContextBuilder:
    """Gathers user evidence, code artifacts, Knowledge Mesh, mistake patterns, and recommendations into bounded grounded context."""

    def build_user_context(self, user_id: str, db: Session, target_artifact_id: str = None, user_query: str = "") -> dict[str, Any]:
        """Construct grounded context dictionary from PostgreSQL database."""
        user = db.query(User).filter(User.id == user_id).first()

        # Classify Intent
        intent: IntentType = QuestionRouter.classify_intent(user_query) if user_query else "GENERAL"

        # Connected platforms & evidence count
        connections = db.query(PlatformConnection).filter(PlatformConnection.user_id == user_id).all()
        connected_platforms = [c.platform for c in connections if c.connected]

        evidence_items = db.query(Evidence).filter(Evidence.user_id == user_id).all()
        evidence_count = len(evidence_items)

        # Detect Mistake Patterns
        detector = MistakeDetectorEngine()
        mistake_patterns = detector.detect_mistake_patterns(user_id, db)

        # Code artifacts & AST analyses
        artifacts = db.query(CodeArtifact).filter(CodeArtifact.user_id == user_id).all()
        artifact_count = len(artifacts)
        artifact_list = []
        for art in artifacts:
            artifact_list.append({
                "id": art.id,
                "repository": art.repository,
                "file_path": art.file_path,
                "language": art.language,
                "source_url": art.source_url,
                "has_recursion": art.analysis.has_recursion if art.analysis else False,
                "detected_concepts": art.analysis.detected_concepts if art.analysis else [],
            })

        # Knowledge Mesh graph data
        builder = KnowledgeMeshGraphBuilder()
        graph = builder.build_graph(user_id, db)

        # Recommendations & Next Best Action
        rec_service = RecommendationService()
        nba = rec_service.get_next_best_action(user_id, db)
        learning_path = rec_service.get_learning_path(user_id, db)

        # Target artifact context if specified by user
        specific_artifact = None
        if target_artifact_id:
            art_obj = db.query(CodeArtifact).filter(CodeArtifact.id == target_artifact_id).first()
            if art_obj:
                specific_artifact = {
                    "id": art_obj.id,
                    "repository": art_obj.repository,
                    "file_path": art_obj.file_path,
                    "code_content": art_obj.code_content,
                    "language": art_obj.language,
                    "analysis": {
                        "has_recursion": art_obj.analysis.has_recursion if art_obj.analysis else False,
                        "detected_concepts": art_obj.analysis.detected_concepts if art_obj.analysis else [],
                        "cyclomatic_complexity": art_obj.analysis.cyclomatic_complexity if art_obj.analysis else 1,
                    } if art_obj.analysis else None,
                }

        return {
            "user_id": user_id,
            "username": (user.full_name or user.email or "developer") if user else "developer",
            "intent": intent,
            "connected_platforms": connected_platforms,
            "evidence_count": evidence_count,
            "artifact_count": artifact_count,
            "artifacts": artifact_list,
            "specific_artifact": specific_artifact,
            "mistake_patterns": mistake_patterns,
            "nodes": [n["data"] for n in graph["nodes"]],
            "next_best_action": nba,
            "learning_path_steps": learning_path["steps"],
            "has_real_evidence": evidence_count > 0 or artifact_count > 0,
        }
