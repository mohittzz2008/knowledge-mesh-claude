import uuid
import pytest
from app.database import SessionLocal
from app.models.user import User
from app.models.platform import PlatformConnection
from app.models.evidence import Evidence
from app.models.problem import Problem, CodeAttempt
from app.models.skill import Skill, SkillAssessment
from app.services.mesh.relationship_engine import seed_controlled_skills_and_relationships
from app.services.recommendations.problem_matcher import ProblemMatcherService, CONTROLLED_PRACTICE_PROBLEMS


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_adaptive_difficulty_low_mastery_10_percent(db_session):
    """TEST 1: 10% mastery -> Easy problems rank above Medium/Hard."""
    uid = uuid.uuid4().hex[:8]
    user = User(clerk_user_id=f"clerk_diff_10_{uid}", email=f"user_10_{uid}@example.com")
    db_session.add(user)
    db_session.commit()

    skills_map = seed_controlled_skills_and_relationships(db_session)
    skill = skills_map["dfs"]

    ass = SkillAssessment(
        user_id=user.id,
        skill_id=skill.id,
        mastery_score=10.0,
        status="weak",
        evidence_count=1,
    )
    db_session.add(ass)
    db_session.commit()

    matcher = ProblemMatcherService()
    recs = matcher.get_ranked_recommendations(user.id, skill.slug, db_session)
    assert len(recs) > 0
    # Easy problem should rank #1 for 10% low mastery when Easy and Medium problems exist
    assert recs[0]["difficulty"] == "Easy"


def test_adaptive_difficulty_medium_mastery_50_percent(db_session):
    """TEST 2: 50% mastery -> Medium problems rank above Easy/Hard."""
    uid = uuid.uuid4().hex[:8]
    user = User(clerk_user_id=f"clerk_diff_50_{uid}", email=f"user_50_{uid}@example.com")
    db_session.add(user)
    db_session.commit()

    skills_map = seed_controlled_skills_and_relationships(db_session)
    skill = skills_map["dfs"]

    ass = SkillAssessment(
        user_id=user.id,
        skill_id=skill.id,
        mastery_score=50.0,
        status="developing",
        evidence_count=5,
    )
    db_session.add(ass)
    db_session.commit()

    matcher = ProblemMatcherService()
    recs = matcher.get_ranked_recommendations(user.id, skill.slug, db_session)
    assert len(recs) > 0
    # Medium problem ("Number of Islands") should rank #1 for 50% mastery
    assert recs[0]["difficulty"] == "Medium"


def test_adaptive_difficulty_high_mastery_85_percent(db_session):
    """TEST 3: 85% mastery -> Hard problems preferred if available, or closest available difficulty."""
    uid = uuid.uuid4().hex[:8]
    user = User(clerk_user_id=f"clerk_diff_85_{uid}", email=f"user_85_{uid}@example.com")
    db_session.add(user)
    db_session.commit()

    skills_map = seed_controlled_skills_and_relationships(db_session)
    skill = skills_map["dfs"]

    ass = SkillAssessment(
        user_id=user.id,
        skill_id=skill.id,
        mastery_score=85.0,
        status="mastered",
        evidence_count=20,
    )
    db_session.add(ass)
    db_session.commit()

    matcher = ProblemMatcherService()
    recs = matcher.get_ranked_recommendations(user.id, skill.slug, db_session)
    assert len(recs) > 0
    # For dfs, Medium ("Number of Islands", dist=1) ranks above Easy (dist=2) for 85% Hard target
    assert recs[0]["difficulty"] in ["Medium", "Hard"]


def test_adaptive_difficulty_soft_fallback_only_easy_exists(db_session):
    """TEST 4: Only Easy problems exist -> Easy problems returned even for high-mastery user."""
    uid = uuid.uuid4().hex[:8]
    user = User(clerk_user_id=f"clerk_fallback_{uid}", email=f"user_fallback_{uid}@example.com")
    db_session.add(user)
    db_session.commit()

    matcher = ProblemMatcherService()
    # "functions" skill only has Easy controlled problems (FLOW001, ATM, GitHub)
    recs = matcher.get_ranked_recommendations(user.id, "functions", db_session, target_difficulty="Hard")
    assert len(recs) > 0, "Recommendations must not be empty when target difficulty is unavailable"
    assert recs[0]["difficulty"] == "Easy"


def test_adaptive_difficulty_connected_easy_vs_nonconnected_medium(db_session):
    """TEST 5: Connected CodeChef Easy vs non-connected Medium for Medium-target user -> Medium problem outranks Easy."""
    uid = uuid.uuid4().hex[:8]
    user = User(clerk_user_id=f"clerk_override_{uid}", email=f"user_override_{uid}@example.com")
    db_session.add(user)
    db_session.commit()

    # User has CodeChef connected
    conn = PlatformConnection(
        user_id=user.id,
        platform="CodeChef",
        username=f"cc_user_{uid}",
        connected=True,
    )
    db_session.add(conn)
    db_session.commit()

    matcher = ProblemMatcherService()
    # For dfs: LeetCode Number of Islands (Medium, Non-connected) vs CodeChef (Easy)
    recs = matcher.get_ranked_recommendations(user.id, "dfs", db_session, target_difficulty="Medium")
    
    assert recs[0]["difficulty"] == "Medium"
    assert recs[0]["platform"] == "CodeChef"
    assert recs[0]["title"] in ["Fire Escape Routes (FIRESC)", "Number of Islands"]


def test_adaptive_difficulty_same_difficulty_connected_platform_preference(db_session):
    """TEST 6: Same difficulty, different platforms -> Connected platform receives preference."""
    uid = uuid.uuid4().hex[:8]
    user = User(clerk_user_id=f"clerk_tiebreak_{uid}", email=f"user_tiebreak_{uid}@example.com")
    db_session.add(user)
    db_session.commit()

    conn = PlatformConnection(
        user_id=user.id,
        platform="CodeChef",
        username=f"cc_user_{uid}",
        connected=True,
    )
    db_session.add(conn)
    db_session.commit()

    matcher = ProblemMatcherService()
    # For "functions": CodeChef (Easy, Connected) vs GitHub (Easy, Non-connected)
    recs = matcher.get_ranked_recommendations(user.id, "functions", db_session, target_difficulty="Easy")
    assert recs[0]["platform"] == "CodeChef", "Connected CodeChef problem should win tiebreaker against non-connected Easy problem"


def test_step10_codechef_solved_exclusion_preserved(db_session):
    """TEST 7: Already solved CodeChef problem -> Step 10 filtering still excludes it."""
    uid = uuid.uuid4().hex[:8]
    user = User(clerk_user_id=f"clerk_solved_cc_{uid}", email=f"user_solved_cc_{uid}@example.com")
    db_session.add(user)
    db_session.commit()

    conn = PlatformConnection(
        user_id=user.id,
        platform="CodeChef",
        username=f"cc_user_{uid}",
        connected=True,
    )
    db_session.add(conn)
    db_session.commit()

    ev = Evidence(
        user_id=user.id,
        platform_connection_id=conn.id,
        external_id=f"codechef_prob_{uid}_FLOW001",
        title="CodeChef Solved Challenge: FLOW001",
        evidence_type="problem_submission",
        normalized_payload={"problem_code": "FLOW001"},
    )
    db_session.add(ev)
    db_session.commit()

    matcher = ProblemMatcherService()
    recs = matcher.get_ranked_recommendations(user.id, "functions", db_session)
    rec_titles = [r["title"] for r in recs]

    assert not any("FLOW001" in t for t in rec_titles), "Step 10 CodeChef solved exclusion must remain active"


def test_step10_leetcode_hackerrank_solved_exclusion_preserved(db_session):
    """TEST 8: Already solved LeetCode/HackerRank problem -> External filtering still works."""
    uid = uuid.uuid4().hex[:8]
    user = User(clerk_user_id=f"clerk_solved_lc_{uid}", email=f"user_solved_lc_{uid}@example.com")
    db_session.add(user)
    db_session.commit()

    conn = PlatformConnection(
        user_id=user.id,
        platform="LeetCode",
        username=f"lc_user_{uid}",
        connected=True,
    )
    db_session.add(conn)
    db_session.commit()

    ev = Evidence(
        user_id=user.id,
        platform_connection_id=conn.id,
        external_id=f"leetcode_sub_contains-duplicate_{uid}",
        title="LeetCode Submission: Contains Duplicate (Accepted)",
        evidence_type="problem_submission",
        normalized_payload={"title_slug": "contains-duplicate"},
    )
    db_session.add(ev)
    db_session.commit()

    matcher = ProblemMatcherService()
    recs = matcher.get_ranked_recommendations(user.id, "arrays", db_session)
    rec_titles = [r["title"] for r in recs]

    assert not any("Contains Duplicate" in t for t in rec_titles), "Step 10 LeetCode solved exclusion must remain active"


def test_step10_internal_codeattempt_exclusion_preserved(db_session):
    """TEST 9: Existing CodeAttempt exclusion -> Internal completed problems remain excluded."""
    uid = uuid.uuid4().hex[:8]
    user = User(clerk_user_id=f"clerk_internal_{uid}", email=f"user_internal_{uid}@example.com")
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

    assert target_problem.id not in rec_ids, "Internal CodeAttempt exclusion must remain active"
