"""Unit and Integration tests for Recommendations, Next Best Action, and Learning Path Services."""

import pytest
from app.services.recommendations.gap_engine import KnowledgeGapEngine
from app.services.recommendations.next_best_action import NextBestActionService
from app.services.recommendations.problem_matcher import ProblemMatcherService
from app.services.recommendations.learning_path_generator import LearningPathGenerator


@pytest.fixture
def db_session():
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_gap_engine_and_next_best_action(db_session):
    gap_engine = KnowledgeGapEngine()
    gaps = gap_engine.find_actionable_gaps("test_user_id", db_session)
    assert len(gaps) > 0

    nba_service = NextBestActionService()
    nba = nba_service.determine_next_best_action("test_user_id", db_session)
    assert "target_skill" in nba
    assert "reason" in nba
    assert "recommended_difficulty" in nba


def test_problem_matcher_and_learning_path(db_session):
    matcher = ProblemMatcherService()
    recs = matcher.get_ranked_recommendations("test_user_id", "recursion", db_session)
    assert len(recs) > 0
    assert "status_label" in recs[0]

    # Test practice recommendations for sets and arrays
    sets_recs = matcher.get_ranked_recommendations("test_user_id", "sets", db_session)
    assert len(sets_recs) > 0

    arrays_recs = matcher.get_ranked_recommendations("test_user_id", "arrays", db_session)
    assert len(arrays_recs) > 0

    generator = LearningPathGenerator()
    roadmap = generator.generate_roadmap("test_user_id", db_session)
    assert "steps" in roadmap
    # Learning path now includes all 17 controlled skills.
    assert len(roadmap["steps"]) == 17

    slugs = [s["slug"] for s in roadmap["steps"]]
    # Original 8
    assert "functions" in slugs
    assert "lists" in slugs
    assert "sets" in slugs
    assert "arrays" in slugs
    assert "recursion" in slugs
    assert "tree-traversal" in slugs
    assert "dfs" in slugs
    assert "graph-algorithms" in slugs
    # 9 newly included
    assert "iteration" in slugs
    assert "dictionaries" in slugs
    assert "hashing" in slugs
    assert "object-oriented-programming" in slugs
    assert "error-handling" in slugs
    assert "python" in slugs
    assert "c" in slugs
    assert "problem-solving" in slugs
    assert "async-programming" in slugs
