"""Unit and Integration tests for CoachContext, AI Provider, and Coach Service."""

import uuid
import pytest
from app.services.coach.context_builder import CoachContextBuilder
from app.services.coach.provider_base import MockGroundedAIProvider
from app.services.coach.coach_service import CoachService
from app.models.user import User


def test_coach_context_builder(db_session):
    # Create a real User row so skill_assessments FK is satisfied.
    test_user_id = f"test-coach-ctx-{uuid.uuid4().hex[:8]}"
    user = User(id=test_user_id, clerk_user_id=f"clerk_{test_user_id}", full_name="Coach Test")
    db_session.add(user)
    db_session.commit()

    try:
        builder = CoachContextBuilder()
        ctx = builder.build_user_context(test_user_id, db_session)
        assert "user_id" in ctx
        assert "connected_platforms" in ctx
        assert "next_best_action" in ctx
    finally:
        from app.models.skill import SkillAssessment
        db_session.query(SkillAssessment).filter(SkillAssessment.user_id == test_user_id).delete()
        db_session.delete(user)
        db_session.commit()


def test_mock_grounded_ai_provider():
    provider = MockGroundedAIProvider()
    dummy_ctx = {
        "user_id": "test_user_id",
        "evidence_count": 5,
        "artifact_count": 2,
        "connected_platforms": ["GitHub"],
        "total_evidence_count": 5,
        "external_evidence_count": 3,
        "codelab_artifacts_count": 2,
        "artifacts": [{"id": "a1", "language": "Python", "repository": "mohit/mesh", "file_path": "main.py"}],
        "next_best_action": {"target_skill": "Recursion", "reason": "Weak evidence", "recommended_difficulty": "Easy"},
    }

    res = provider.generate_response(dummy_ctx, "Why am I weak at recursion?")
    assert "answer" in res
    assert "Recursion" in res["answer"]
    assert len(res["suggested_actions"]) > 0


def test_coach_service_message_persistence(db_session, monkeypatch):
    # Create a real User row so coach_conversations FK is satisfied.
    test_user_id = f"test-coach-svc-{uuid.uuid4().hex[:8]}"
    user = User(id=test_user_id, clerk_user_id=f"clerk_{test_user_id}", full_name="Coach Svc Test")
    db_session.add(user)
    db_session.commit()

    monkeypatch.setattr(
        "app.services.coach.coach_service.get_ai_provider", lambda: MockGroundedAIProvider()
    )

    try:
        service = CoachService()
        res = service.process_user_message(
            user_id=test_user_id,
            message="What should I practice today?",
            db=db_session,
        )
        assert "conversation_id" in res
        assert "answer" in res

        history = service.get_conversation_history(res["conversation_id"], test_user_id, db_session)
        assert len(history["messages"]) == 2  # user msg + ai msg
    finally:
        from app.models.coach import CoachConversation, CoachMessage
        from app.models.skill import SkillAssessment
        db_session.query(CoachMessage).filter(
            CoachMessage.conversation_id.in_(
                db_session.query(CoachConversation.id).filter(CoachConversation.user_id == test_user_id)
            )
        ).delete(synchronize_session=False)
        db_session.query(CoachConversation).filter(CoachConversation.user_id == test_user_id).delete()
        db_session.query(SkillAssessment).filter(SkillAssessment.user_id == test_user_id).delete()
        db_session.delete(user)
        db_session.commit()


def test_coach_without_provider_saves_nothing(db_session, monkeypatch):
    """No AI key configured: fail before persisting anything (no orphaned user message)."""
    from app.models.coach import CoachConversation, CoachMessage
    from app.services.coach.provider_base import CoachUnavailableError

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    before_c = db_session.query(CoachConversation).count()
    before_m = db_session.query(CoachMessage).count()

    with pytest.raises(CoachUnavailableError):
        CoachService().process_user_message(user_id="u-no-provider", message="hello coach", db=db_session)

    assert db_session.query(CoachConversation).count() == before_c
    assert db_session.query(CoachMessage).count() == before_m


def test_mock_provider_code_lab_intent_does_not_crash():
    """Regression: the CODE_LAB branch referenced an undefined `ev_count`."""
    res = MockGroundedAIProvider().generate_response(
        {"intent": "CODE_LAB", "evidence_count": 3, "connected_platforms": []}, "give me a hint"
    )
    assert "Hints" in res["answer"]
    assert res["confidence"] > 0
