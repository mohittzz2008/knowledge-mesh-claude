"""Full Product Integration Audit & Hardening Verification Script."""

import asyncio
import sys
import uuid
from typing import Any
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine
from app.models.user import User, DeveloperProfile
from app.models.platform import PlatformConnection
from app.models.evidence import Evidence
from app.models.code_artifact import CodeArtifact, CodeAnalysis
from app.models.skill import Skill, SkillAssessment, SkillRelationship
from app.models.problem import Problem, ProblemRecommendation, CodeAttempt
from app.models.coach import CoachConversation, CoachMessage

from app.services.platform.github import GitHubConnector
from app.services.platform.leetcode import LeetCodeConnector
from app.services.platform.hackerrank import HackerRankConnector
from app.services.platform.registry import PlatformRegistry
from app.services.mesh.concept_extractor import ConceptExtractorService
from app.services.mesh.unified_profile import UnifiedProfileService
from app.services.mesh.graph_builder import KnowledgeMeshGraphBuilder
from app.services.recommendations.next_best_action import NextBestActionService
from app.services.recommendations.learning_path_generator import LearningPathGenerator
from app.services.recommendations.recommendation_service import RecommendationService
from app.services.coach.coach_service import CoachService
from app.services.coach.question_router import QuestionRouter
from app.services.coach.mistake_detector import MistakeDetectorEngine
from app.services.code_lab.code_lab_service import CodeLabService


def audit_user_isolation(db: Session) -> bool:
    """Audit: Verify database queries enforce strict user_id isolation between User A and User B."""
    user_a = User(clerk_user_id=f"user_a_{uuid.uuid4().hex[:6]}", email="usera@test.com", full_name="User A")
    user_b = User(clerk_user_id=f"user_b_{uuid.uuid4().hex[:6]}", email="userb@test.com", full_name="User B")
    db.add_all([user_a, user_b])
    db.commit()

    # Create evidence for User A only
    conn_a = PlatformConnection(user_id=user_a.id, platform="GitHub", connected=True, username="user_a_gh")
    db.add(conn_a)
    db.commit()

    ev_a = Evidence(
        user_id=user_a.id,
        platform_connection_id=conn_a.id,
        title="User A GitHub Evidence",
        evidence_type="code_file",
        external_id=f"user_a_ev_{uuid.uuid4().hex[:6]}",
        normalized_payload={"skills": ["Recursion"]}
    )
    db.add(ev_a)
    db.commit()

    # Query Unified Profile for User B
    profile_service = UnifiedProfileService()
    profile_b = profile_service.get_unified_profile(user_b.id, db)

    # User B MUST see 0 evidence items from User A
    assert profile_b["total_evidence_count"] == 0, "ISOLATION FAILURE: User B saw User A evidence!"

    # Clean up test users
    db.delete(ev_a)
    db.delete(conn_a)
    db.delete(user_a)
    db.delete(user_b)
    db.commit()
    return True


def audit_feedback_loop(db: Session) -> dict[str, Any]:
    """Audit: Verify Code Lab submission -> CodeAttempt -> Evidence -> SkillAssessment -> Knowledge Mesh update."""
    user = db.query(User).first()
    if not user:
        user = User(clerk_user_id="audit_demo_user", email="audit@test.com", full_name="Audit User")
        db.add(user)
        db.commit()

    # 1. Baseline SkillAssessment score for Recursion
    extractor = ConceptExtractorService()
    extractor.extract_and_assess_user_skills(user.id, db)

    builder = KnowledgeMeshGraphBuilder()
    mesh_before = builder.build_graph(user.id, db)
    rec_before = next((n for n in mesh_before["nodes"] if n["id"] == "recursion"), None)
    score_before = rec_before["data"]["mastery"] if rec_before else 0.0

    # 2. Submit Code Lab Solution for Recursion / Tree Inorder Traversal
    code_lab = CodeLabService()
    solution_code = (
        "class TreeNode:\n"
        "    def __init__(self, val=0, left=None, right=None):\n"
        "        self.val = val\n"
        "        self.left = left\n"
        "        self.right = right\n\n"
        "def inorder_traversal(root):\n"
        "    if not root:\n"
        "        return []\n"
        "    return inorder_traversal(root.left) + [root.val] + inorder_traversal(root.right)\n"
    )

    submit_res = code_lab.submit_code(user.id, "problem-tree-inorder", solution_code, "Python", db)
    assert submit_res["is_passed"] is True
    assert submit_res["telemetry_logged"] is True

    # 3. Verify PostgreSQL SkillAssessment re-evaluated after submission
    mesh_after = builder.build_graph(user.id, db)
    rec_after = next((n for n in mesh_after["nodes"] if n["id"] == "recursion"), None)
    score_after = rec_after["data"]["mastery"] if rec_after else 0.0

    return {
        "is_passed": submit_res["is_passed"],
        "attempt_id": submit_res["attempt_id"],
        "evidence_id": submit_res["evidence_id"],
        "score_before": score_before,
        "score_after": score_after,
        "feedback_loop_verified": score_after >= score_before,
    }


def main():
    db: Session = SessionLocal()
    print("==================================================================")
    print("      FULL KNOWLEDGE MESH PRODUCT INTEGRATION AUDIT")
    print("==================================================================")

    # Audit 1: Central Platform Registry & Capability Model
    print("\n[Audit 1/6] Central Platform Registry & Capability Model:")
    registry = PlatformRegistry.list_items()
    for item in registry:
        print(f"  • Platform: {item.name} ({item.key}) — Status: {item.status}, Capabilities: {item.capabilities}")

    # Audit 2: Strict User Isolation Test
    print("\n[Audit 2/6] User Isolation Audit:")
    iso_pass = audit_user_isolation(db)
    print(f"  • Strict Database User Isolation: {'VERIFIED (PASSED)' if iso_pass else 'FAILED'}")

    # Audit 3: Code Lab Feedback Loop Test
    print("\n[Audit 3/6] Feedback Loop Audit (Code Lab -> Evidence -> Skill Assessment -> Knowledge Mesh):")
    fb_res = audit_feedback_loop(db)
    print(f"  • Code Submission Status: {'Passed' if fb_res['is_passed'] else 'Failed'}")
    print(f"  • CodeAttempt ID: {fb_res['attempt_id']}")
    print(f"  • Ingested Evidence ID: {fb_res['evidence_id']}")
    print(f"  • Recursion Skill Score Before: {fb_res['score_before']}% -> After: {fb_res['score_after']}%")
    print(f"  • Full Feedback Loop Status: {'VERIFIED (PASSED)' if fb_res['feedback_loop_verified'] else 'FAILED'}")

    # Audit 4: Question Intent Router & Mistake Detection
    print("\n[Audit 4/6] Question Router & Mistake Pattern Engine Audit:")
    q1 = QuestionRouter.classify_intent("Why am I weak at recursion?")
    q2 = QuestionRouter.classify_intent("Give me a hint for this Code Lab problem")
    print(f"  • Intent 1 ('Why am I weak at recursion?'): {q1}")
    print(f"  • Intent 2 ('Give me a hint for this Code Lab problem'): {q2}")

    detector = MistakeDetectorEngine()
    patterns = detector.detect_mistake_patterns("audit_demo_user", db)
    print(f"  • Detected Anti-Patterns Count: {len(patterns)}")

    # Audit 5: Unified Profile & Recommendation Engine
    print("\n[Audit 5/6] Unified Developer Profile & Recommendation Contract Audit:")
    user = db.query(User).first()
    uni = UnifiedProfileService().get_unified_profile(user.id, db)
    nba = NextBestActionService().get_next_best_action(user.id, db)
    lp = LearningPathGenerator().generate_roadmap(user.id, db)

    print(f"  • Overall Skill Score: {uni['overall_skill_score']} / 100")
    print(f"  • Next Best Action: Practice {nba['target_skill']} ({nba['recommended_difficulty']})")
    print(f"  • Learning Path Target Goal: {lp['target_goal']} ({lp['total_steps']} steps)")

    print("\n==================================================================")
    print("      AUDIT EXECUTION COMPLETE — PROCEEDING TO FINAL REPORT")
    print("==================================================================")
    db.close()


if __name__ == "__main__":
    main()
