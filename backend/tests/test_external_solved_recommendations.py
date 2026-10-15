import uuid
import pytest
from app.database import SessionLocal
from app.models.user import User
from app.models.platform import PlatformConnection
from app.models.evidence import Evidence
from app.models.problem import Problem, CodeAttempt
from app.services.recommendations.problem_matcher import ProblemMatcherService, CONTROLLED_PRACTICE_PROBLEMS


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_recommendation_unsolved_flow001(db_session):
    """TEST 1: User has not solved FLOW001 externally -> FLOW001 may be recommended."""
    uid = uuid.uuid4().hex[:8]
    user = User(clerk_user_id=f"clerk_unsolved_{uid}", email=f"test1_{uid}@example.com")
    db_session.add(user)
    db_session.commit()

    conn = PlatformConnection(
        user_id=user.id,
        platform="CodeChef",
        username=f"test_cc_user_1_{uid}",
        connected=True,
    )
    db_session.add(conn)
    db_session.commit()

    matcher = ProblemMatcherService()
    recs = matcher.get_ranked_recommendations(user.id, "functions", db_session)
    rec_titles = [r["title"] for r in recs]

    assert any("FLOW001" in t for t in rec_titles), "FLOW001 should be recommended when unsolved"


def test_recommendation_solved_flow001(db_session):
    """TEST 2: User has solved FLOW001 on CodeChef -> FLOW001 must NOT be recommended."""
    uid = uuid.uuid4().hex[:8]
    user = User(clerk_user_id=f"clerk_flow001_{uid}", email=f"test2_{uid}@example.com")
    db_session.add(user)
    db_session.commit()

    conn = PlatformConnection(
        user_id=user.id,
        platform="CodeChef",
        username=f"test_cc_user_2_{uid}",
        connected=True,
    )
    db_session.add(conn)
    db_session.commit()

    # Create CodeChef Evidence for solved FLOW001
    ev = Evidence(
        user_id=user.id,
        platform_connection_id=conn.id,
        external_id=f"codechef_prob_test_FLOW001_{uid}",
        title="CodeChef Solved Challenge: Add Two Numbers (FLOW001)",
        evidence_type="problem_submission",
        normalized_payload={
            "problem_code": "FLOW001",
            "problem_title": "Add Two Numbers (FLOW001)",
            "status": "Solved",
            "passed": True,
            "skills": ["functions", "math", "problem-solving"],
        },
    )
    db_session.add(ev)
    db_session.commit()

    matcher = ProblemMatcherService()
    recs = matcher.get_ranked_recommendations(user.id, "functions", db_session)
    rec_titles = [r["title"] for r in recs]

    assert not any("FLOW001" in t for t in rec_titles), "FLOW001 MUST NOT be recommended when already solved externally"


def test_recommendation_solved_atm(db_session):
    """TEST 3: User has solved ATM on CodeChef -> ATM must NOT be recommended."""
    uid = uuid.uuid4().hex[:8]
    user = User(clerk_user_id=f"clerk_atm_{uid}", email=f"test3_{uid}@example.com")
    db_session.add(user)
    db_session.commit()

    conn = PlatformConnection(
        user_id=user.id,
        platform="CodeChef",
        username=f"test_cc_user_3_{uid}",
        connected=True,
    )
    db_session.add(conn)
    db_session.commit()

    ev = Evidence(
        user_id=user.id,
        platform_connection_id=conn.id,
        external_id=f"codechef_prob_test_ATM_{uid}",
        title="CodeChef Solved Challenge: ATM (ATM)",
        evidence_type="problem_submission",
        normalized_payload={
            "problem_code": "ATM",
            "problem_title": "ATM (ATM)",
            "status": "Solved",
            "passed": True,
            "skills": ["functions", "problem-solving"],
        },
    )
    db_session.add(ev)
    db_session.commit()

    matcher = ProblemMatcherService()
    recs = matcher.get_ranked_recommendations(user.id, "functions", db_session)
    rec_titles = [r["title"] for r in recs]

    assert not any("ATM" in t for t in rec_titles), "ATM MUST NOT be recommended when already solved externally"


def test_recommendation_solved_both_flow001_and_atm(db_session):
    """TEST 4: User has solved both FLOW001 and ATM -> Neither should be recommended."""
    uid = uuid.uuid4().hex[:8]
    user = User(clerk_user_id=f"clerk_both_{uid}", email=f"test4_{uid}@example.com")
    db_session.add(user)
    db_session.commit()

    conn = PlatformConnection(
        user_id=user.id,
        platform="CodeChef",
        username=f"test_cc_user_4_{uid}",
        connected=True,
    )
    db_session.add(conn)
    db_session.commit()

    ev1 = Evidence(
        user_id=user.id,
        platform_connection_id=conn.id,
        external_id=f"codechef_prob_test_FLOW001_{uid}",
        title="CodeChef Solved Challenge: Add Two Numbers (FLOW001)",
        evidence_type="problem_submission",
        normalized_payload={"problem_code": "FLOW001", "problem_title": "FLOW001"},
    )
    ev2 = Evidence(
        user_id=user.id,
        platform_connection_id=conn.id,
        external_id=f"codechef_prob_test_ATM_{uid}",
        title="CodeChef Solved Challenge: ATM (ATM)",
        evidence_type="problem_submission",
        normalized_payload={"problem_code": "ATM", "problem_title": "ATM"},
    )
    db_session.add_all([ev1, ev2])
    db_session.commit()

    matcher = ProblemMatcherService()
    recs = matcher.get_ranked_recommendations(user.id, "functions", db_session)
    rec_titles = [r["title"] for r in recs]

    assert not any("FLOW001" in t for t in rec_titles), "FLOW001 MUST NOT be recommended"
    assert not any("ATM" in t for t in rec_titles), "ATM MUST NOT be recommended"


def test_recommendation_internal_codeattempt_exclusion(db_session):
    """TEST 5: User has completed an internal CodeLab problem -> Existing CodeAttempt exclusion continues to work."""
    uid = uuid.uuid4().hex[:8]
    user = User(clerk_user_id=f"clerk_codelab_{uid}", email=f"test5_{uid}@example.com")
    db_session.add(user)
    db_session.commit()

    matcher = ProblemMatcherService()
    problems = matcher.seed_problems(db_session)
    target_problem = problems[0]

    attempt = CodeAttempt(
        user_id=user.id,
        problem_id=target_problem.id,
        status="completed",
        source_platform="CodeLab",
    )
    db_session.add(attempt)
    db_session.commit()

    recs = matcher.get_ranked_recommendations(user.id, "all", db_session)
    rec_ids = [r["problem_id"] for r in recs]

    assert target_problem.id not in rec_ids, "Completed CodeAttempt problem must be excluded from recommendations"


def test_recommendation_external_solved_no_codeattempts(db_session):
    """TEST 6: User has external solved problems but no internal CodeAttempts -> External solved filtering still works."""
    uid = uuid.uuid4().hex[:8]
    user = User(clerk_user_id=f"clerk_ext_only_{uid}", email=f"test6_{uid}@example.com")
    db_session.add(user)
    db_session.commit()

    conn = PlatformConnection(
        user_id=user.id,
        platform="CodeChef",
        username=f"test_cc_user_6_{uid}",
        connected=True,
    )
    db_session.add(conn)
    db_session.commit()

    ev = Evidence(
        user_id=user.id,
        platform_connection_id=conn.id,
        external_id=f"codechef_prob_test_FLOW001_{uid}",
        title="CodeChef Solved Challenge: FLOW001",
        evidence_type="problem_submission",
        normalized_payload={"problem_code": "FLOW001"},
    )
    db_session.add(ev)
    db_session.commit()

    # Confirm 0 CodeAttempts exist for user
    attempts_count = db_session.query(CodeAttempt).filter(CodeAttempt.user_id == user.id).count()
    assert attempts_count == 0

    matcher = ProblemMatcherService()
    recs = matcher.get_ranked_recommendations(user.id, "functions", db_session)
    rec_titles = [r["title"] for r in recs]

    assert not any("FLOW001" in t for t in rec_titles), "External solved filtering must work even with 0 internal CodeAttempts"
