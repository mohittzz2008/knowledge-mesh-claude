"""Unit and Integration tests for Deep Personalized AI Coach Intelligence."""

import pytest
from app.services.coach.question_router import QuestionRouter
from app.services.coach.mistake_detector import MistakeDetectorEngine
from app.services.coach.context_builder import CoachContextBuilder
from app.services.coach.provider_base import MockGroundedAIProvider


def test_question_router():
    assert QuestionRouter.classify_intent("Why do you think my recursion is strong?") == "SKILL"
    assert QuestionRouter.classify_intent("Show evidence for my skills") == "EVIDENCE"
    assert QuestionRouter.classify_intent("What should I practice next?") == "RECOMMENDATION"
    assert QuestionRouter.classify_intent("Give me a hint for this Code Lab problem") == "CODE_LAB"
    assert QuestionRouter.classify_intent("How am I doing on LeetCode?") == "PLATFORM"


def test_mistake_detector_engine(db_session):
    engine = MistakeDetectorEngine()
    patterns = engine.detect_mistake_patterns("test_user_id", db_session)
    assert isinstance(patterns, list)


def test_mock_grounded_ai_provider():
    provider = MockGroundedAIProvider()
    ctx = {
        "intent": "SKILL",
        "evidence_count": 10,
        "artifact_count": 4,
        "connected_platforms": ["GitHub", "LeetCode"],
        "next_best_action": {"target_skill": "Recursion", "reason": "Strong evidence"},
    }
    res = provider.generate_response(ctx, "Why am I weak at recursion?")
    assert "answer" in res
    assert res["confidence"] >= 0.8
    assert "evidence_references" in res
