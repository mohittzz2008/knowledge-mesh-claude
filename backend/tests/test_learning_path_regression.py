"""Focused regression tests for Learning Path evidence selection, status rules, and prerequisite locking."""

import uuid
from datetime import datetime, timezone, timedelta
import pytest
from app.models.user import User
from app.models.skill import Skill, SkillAssessment, SkillRelationship, get_latest_user_assessments
from app.services.mesh.relationship_engine import seed_controlled_skills_and_relationships
from app.services.mesh.graph_builder import KnowledgeMeshGraphBuilder
from app.services.recommendations.learning_path_generator import LearningPathGenerator


@pytest.fixture
def test_user(db_session):
    """Create an isolated test user and clean up after the test."""
    uid = f"test-lp-{uuid.uuid4().hex[:12]}"
    user = User(
        id=uid,
        clerk_user_id=f"clerk_{uid}",
        email=f"{uid}@example.com",
        full_name="Learning Path Test User",
    )
    db_session.add(user)
    db_session.commit()
    yield user

    # Cleanup
    db_session.query(SkillAssessment).filter(SkillAssessment.user_id == uid).delete()
    db_session.delete(user)
    db_session.commit()


def test_duplicate_assessments_selection_latest_wins(db_session, test_user):
    """Test that when duplicate assessments exist, latest evaluated_at record is deterministically selected."""
    skill_map = seed_controlled_skills_and_relationships(db_session)
    fn_skill = skill_map["functions"]

    now = datetime.now(timezone.utc)
    older_time = now - timedelta(days=2)
    newer_time = now - timedelta(hours=1)

    # Insert older zero-evidence assessment
    old_ass = SkillAssessment(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        skill_id=fn_skill.id,
        mastery_score=0.0,
        status="NO_EVIDENCE",
        evidence_count=0,
        evaluated_at=older_time,
    )
    # Insert newer valid-evidence assessment
    new_ass = SkillAssessment(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        skill_id=fn_skill.id,
        mastery_score=85.0,
        status="mastered",
        evidence_count=8,
        evaluated_at=newer_time,
    )
    db_session.add_all([old_ass, new_ass])
    db_session.commit()

    # Verify get_latest_user_assessments
    latest = get_latest_user_assessments(db_session, test_user.id)
    assert fn_skill.id in latest
    selected = latest[fn_skill.id]
    assert selected.id == new_ass.id
    assert selected.evidence_count == 8
    assert selected.mastery_score == 85.0
    assert selected.status == "mastered"


def test_learning_path_status_calculation_using_latest_assessment(db_session, test_user):
    """Test Learning Path generator correctly uses the latest assessment rather than stale duplicates."""
    skill_map = seed_controlled_skills_and_relationships(db_session)
    fn_skill = skill_map["functions"]

    now = datetime.now(timezone.utc)
    old_ass = SkillAssessment(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        skill_id=fn_skill.id,
        mastery_score=0.0,
        status="NO_EVIDENCE",
        evidence_count=0,
        evaluated_at=now - timedelta(days=1),
    )
    new_ass = SkillAssessment(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        skill_id=fn_skill.id,
        mastery_score=90.0,
        status="mastered",
        evidence_count=12,
        evaluated_at=now,
    )
    db_session.add_all([old_ass, new_ass])
    db_session.commit()

    generator = LearningPathGenerator()
    roadmap = generator.generate_roadmap(test_user.id, db_session)

    fn_step = next(s for s in roadmap["steps"] if s["slug"] == "functions")
    assert fn_step["status"] == "completed"
    assert fn_step["mastery"] == 90
    assert fn_step["evidence_count"] == 12


def test_prerequisite_locking_and_unlocking(db_session, test_user):
    """Test that skills with unmet prerequisites remain locked, and unlock when prerequisites are satisfied."""
    skill_map = seed_controlled_skills_and_relationships(db_session)
    fn_skill = skill_map["functions"]
    rec_skill = skill_map["recursion"]

    now = datetime.now(timezone.utc)

    # 1. Initially, functions has no evidence. recursion depends on functions.
    # Recursion should be locked.
    generator = LearningPathGenerator()
    roadmap_initial = generator.generate_roadmap(test_user.id, db_session)
    rec_step = next(s for s in roadmap_initial["steps"] if s["slug"] == "recursion")
    assert rec_step["status"] == "locked"

    # 2. Add verified evidence for functions (mastered, ev > 0)
    fn_ass = SkillAssessment(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        skill_id=fn_skill.id,
        mastery_score=80.0,
        status="mastered",
        evidence_count=5,
        evaluated_at=now,
    )
    db_session.add(fn_ass)
    db_session.commit()

    roadmap_after_fn = generator.generate_roadmap(test_user.id, db_session)
    fn_step = next(s for s in roadmap_after_fn["steps"] if s["slug"] == "functions")
    assert fn_step["status"] == "completed"

    # Now recursion's prerequisite (functions) is satisfied!
    # If recursion itself is given evidence (e.g. 40%), it should become in_progress
    rec_ass = SkillAssessment(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        skill_id=rec_skill.id,
        mastery_score=40.0,
        status="developing",
        evidence_count=2,
        evaluated_at=now,
    )
    db_session.add(rec_ass)
    db_session.commit()

    roadmap_with_rec = generator.generate_roadmap(test_user.id, db_session)
    rec_step_after = next(s for s in roadmap_with_rec["steps"] if s["slug"] == "recursion")
    assert rec_step_after["status"] == "in_progress"
    assert rec_step_after["mastery"] == 40
    assert rec_step_after["evidence_count"] == 2


def test_skills_with_no_evidence_not_marked_completed(db_session, test_user):
    """Test that a skill is NOT marked completed merely because it has an assessment row if evidence_count == 0."""
    skill_map = seed_controlled_skills_and_relationships(db_session)
    fn_skill = skill_map["functions"]

    now = datetime.now(timezone.utc)
    # Malformed row: status says 'mastered' but evidence_count is 0
    fake_ass = SkillAssessment(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        skill_id=fn_skill.id,
        mastery_score=100.0,
        status="mastered",
        evidence_count=0,
        evaluated_at=now,
    )
    db_session.add(fake_ass)
    db_session.commit()

    generator = LearningPathGenerator()
    roadmap = generator.generate_roadmap(test_user.id, db_session)

    fn_step = next(s for s in roadmap["steps"] if s["slug"] == "functions")
    # Must NOT be completed because ev_count == 0
    assert fn_step["status"] != "completed"


def test_progress_counts_strong_milestones(db_session, test_user):
    """Test that completed count accurately reflects skills with verified evidence and >= 75% mastery."""
    skill_map = seed_controlled_skills_and_relationships(db_session)
    now = datetime.now(timezone.utc)

    # 1. Zero evidence user
    generator = LearningPathGenerator()
    roadmap_zero = generator.generate_roadmap(test_user.id, db_session)
    completed_zero = len([s for s in roadmap_zero["steps"] if s["status"] == "completed"])
    assert completed_zero == 0

    # 2. Add 2 mastered skills (ev > 0, mastery >= 75) and 1 developing skill (ev > 0, mastery 40)
    ass1 = SkillAssessment(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        skill_id=skill_map["functions"].id,
        mastery_score=85.0,
        status="mastered",
        evidence_count=5,
        evaluated_at=now,
    )
    ass2 = SkillAssessment(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        skill_id=skill_map["problem-solving"].id,
        mastery_score=95.0,
        status="mastered",
        evidence_count=10,
        evaluated_at=now,
    )
    ass3 = SkillAssessment(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        skill_id=skill_map["lists"].id,
        mastery_score=40.0,
        status="developing",
        evidence_count=2,
        evaluated_at=now,
    )
    db_session.add_all([ass1, ass2, ass3])
    db_session.commit()

    roadmap = generator.generate_roadmap(test_user.id, db_session)
    completed_steps = [s for s in roadmap["steps"] if s["status"] == "completed"]
    assert len(completed_steps) == 2
    assert {s["slug"] for s in completed_steps} == {"functions", "problem-solving"}

    in_progress_steps = [s for s in roadmap["steps"] if s["status"] == "in_progress"]
    assert any(s["slug"] == "lists" for s in in_progress_steps)
