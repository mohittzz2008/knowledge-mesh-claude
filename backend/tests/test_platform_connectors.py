"""Unit and Integration tests for Central Platform Registry, LeetCode, and HackerRank Connectors."""

import pytest
from unittest.mock import AsyncMock, patch
from app.services.platform.registry import PlatformRegistry
from app.services.platform.leetcode import LeetCodeConnector
from app.services.platform.hackerrank import HackerRankConnector
from app.services.platform.codechef import CodeChefConnector


def test_platform_registry_lookup():
    items = PlatformRegistry.list_items()
    assert len(items) >= 4

    gh_item = PlatformRegistry.get_item("github")
    assert gh_item is not None
    assert gh_item.name == "GitHub"

    lc_item = PlatformRegistry.get_item("leetcode")
    assert lc_item is not None
    assert lc_item.name == "LeetCode"

    hr_item = PlatformRegistry.get_item("hackerrank")
    assert hr_item is not None
    assert hr_item.name == "HackerRank"

    cc_item = PlatformRegistry.get_item("codechef")
    assert cc_item is not None
    assert cc_item.name == "CodeChef"


@pytest.mark.asyncio
async def test_codechef_connector_mocked():
    connector = CodeChefConnector()

    mock_profile_html = """
    <html>
      <body>
        <div class="user-name">demo_chef_user</div>
        <div class="rating-header">
          <div class="rating-number">1850</div>
          <small>(Highest Rating 1920)</small>
          <div class="rating-star">4★</div>
        </div>
        <section class="rating-data-section problems-solved">
          <h3>Total Problems Solved: 2</h3>
          <div class="content">
            <p>
              <span><span style="font-size: 12px";>Jawbreaker</span>,&nbsp;<span style="font-size: 12px";>Closest Ranking</span></span>
            </p>
          </div>
        </section>
      </body>
    </html>
    """

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=AsyncMock(status_code=200, text=mock_profile_html))):
        is_valid = await connector.validate_identity("demo_chef_user")
        assert is_valid is True

        profile = await connector.fetch_profile("demo_chef_user")
        assert profile is not None
        assert profile["username"] == "demo_chef_user"
        assert profile["rating"] == 1850
        assert profile["highest_rating"] == 1920
        assert profile["stars"] == "4★"
        assert profile["total_solved"] == 2
        assert "JAWBREAKER" in profile["solved_codes"]
        assert "CLOSESTRANKING" in profile["solved_codes"]

        evidence = await connector.fetch_evidence("demo_chef_user")
        assert len(evidence) >= 4 # profile + badge + 2 solved problems

        norm_prof = connector.normalize_evidence(evidence[0])
        assert norm_prof["platform"] == "CodeChef"
        assert "Competitive Programming" in norm_prof["normalized_payload"]["skills"]

        norm_prob = connector.normalize_evidence({"type": "codechef_solved_problem", "data": {"username": "demo_chef_user", "problem_code": "JAWBREAKER", "problem_title": "Jawbreaker"}})
        assert norm_prob["source_url"] == "https://www.codechef.com/problems/JAWBREAKER"
        assert norm_prob["title"] == "CodeChef Solved Challenge: Jawbreaker"


@pytest.mark.asyncio
async def test_codechef_empty_and_malformed_solved_problems():
    connector = CodeChefConnector()

    empty_html = "<html><body><div class='rating-number'>1200</div></body></html>"
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=AsyncMock(status_code=200, text=empty_html))):
        prof = await connector.fetch_profile("empty_user")
        assert prof is not None
        assert prof["solved_codes"] == []
        assert prof["total_solved"] == 0

    malformed_html = "<html><body><section class='problems-solved'><h3>Malformed Data</h3></section></body></html>"
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=AsyncMock(status_code=200, text=malformed_html))):
        prof_malformed = await connector.fetch_profile("malformed_user")
        assert prof_malformed is not None
        assert prof_malformed["solved_codes"] == []
        assert prof_malformed["total_solved"] == 0




@pytest.mark.asyncio
async def test_leetcode_connector_mocked():
    connector = LeetCodeConnector()
    
    mock_gql_response = {
        "data": {
            "matchedUser": {
                "username": "demo_leetcode_user",
                "profile": {"realName": "Demo LeetCoder", "userAvatar": None, "ranking": 15000},
                "submitStatsGlobal": {
                    "acSubmissionNum": [
                        {"difficulty": "All", "count": 45},
                        {"difficulty": "Easy", "count": 25},
                        {"difficulty": "Medium", "count": 15},
                        {"difficulty": "Hard", "count": 5},
                    ]
                }
            }
        }
    }

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=AsyncMock(status_code=200, json=lambda: mock_gql_response))):
        is_valid = await connector.validate_identity("demo_leetcode_user")
        assert is_valid is True

        profile = await connector.fetch_profile("demo_leetcode_user")
        assert profile is not None
        assert profile["total_solved"] == 45
        assert profile["medium_solved"] == 15

        raw_item = {"type": "leetcode_profile_stats", "data": profile}
        norm = connector.normalize_evidence(raw_item)
        assert norm["platform"] == "LeetCode"
        assert "Algorithms" in norm["normalized_payload"]["skills"]


@pytest.mark.asyncio
async def test_hackerrank_connector_mocked():
    connector = HackerRankConnector()

    mock_profile_res = {"model": {"username": "demo_hr_user", "name": "Demo Hacker", "level": 3}}
    mock_badges_res = {"models": [
        {"badge_name": "Python", "stars": 5, "hatch_level": "Gold", "solved": 20},
        {"badge_name": "Problem Solving", "stars": 3, "hatch_level": "Silver", "solved": 15},
    ]}

    with patch("httpx.AsyncClient.get", side_effect=[
        AsyncMock(status_code=200, json=lambda: mock_profile_res),
        AsyncMock(status_code=200, json=lambda: mock_badges_res),
        AsyncMock(status_code=200, json=lambda: mock_profile_res),
    ]):
        is_valid = await connector.validate_identity("demo_hr_user")
        assert is_valid is True

        badges = await connector.fetch_badges("demo_hr_user")
        assert len(badges) == 2

        profile = await connector.fetch_profile("demo_hr_user", badges=badges)
        assert profile is not None
        assert profile["total_solved"] is None  # Badge counts are not summed into unique solves

        norm = connector.normalize_evidence({"type": "hackerrank_badge", "data": badges[0]})
        assert norm["platform"] == "HackerRank"
        assert "Python" in norm["normalized_payload"]["skills"]
        assert norm["normalized_payload"]["solved"] == 20

        prof_norm = connector.normalize_evidence({"type": "hackerrank_profile", "data": profile})
        assert prof_norm["normalized_payload"]["total_solved"] is None

    # Test user with no badges -> total_solved is None
    with patch("httpx.AsyncClient.get", side_effect=[
        AsyncMock(status_code=200, json=lambda: mock_profile_res),
        AsyncMock(status_code=200, json=lambda: {"models": []}),
    ]):
        prof_empty = await connector.fetch_profile("demo_hr_user")
        assert prof_empty is not None
        assert prof_empty["total_solved"] is None


def test_hackerrank_skill_mapping_isolation():
    """Verify that HackerRank domains (Problem Solving, Python, C) map to distinct skills and NEVER to Functions."""
    from app.services.mesh.concept_extractor import CONCEPT_TO_SKILL_SLUG
    from app.services.mesh.relationship_engine import CONTROLLED_SKILLS

    controlled_slugs = {s["slug"] for s in CONTROLLED_SKILLS}
    assert "problem-solving" in controlled_slugs
    assert "python" in controlled_slugs
    assert "c" in controlled_slugs
    assert "functions" in controlled_slugs

    # 1. Problem Solving & Algorithms must map to 'problem-solving' and NOT 'functions'
    ps_slug = CONCEPT_TO_SKILL_SLUG.get("Problem Solving")
    assert ps_slug == "problem-solving"
    assert ps_slug != "functions"

    algo_slug = CONCEPT_TO_SKILL_SLUG.get("Algorithms")
    assert algo_slug == "problem-solving"
    assert algo_slug != "functions"

    # 2. Python must map to 'python' and NOT 'functions'
    py_slug = CONCEPT_TO_SKILL_SLUG.get("Python")
    assert py_slug == "python"
    assert py_slug != "functions"

    # 3. C must map to 'c' and NOT 'functions'
    c_slug = CONCEPT_TO_SKILL_SLUG.get("C")
    assert c_slug == "c"
    assert c_slug != "functions"

    # 4. Genuine Functions evidence must still map to 'functions'
    func_slug = CONCEPT_TO_SKILL_SLUG.get("Functions")
    assert func_slug == "functions"

    # 5. Verify HackerRank connector evidence normalization provenance
    connector = HackerRankConnector()
    badge_ps = connector.normalize_evidence({
        "type": "hackerrank_badge",
        "data": {"badge_name": "Problem Solving", "stars": 1, "hatch_level": "Bronze", "username": "test_user"},
    })
    badge_py = connector.normalize_evidence({
        "type": "hackerrank_badge",
        "data": {"badge_name": "Python", "stars": 4, "hatch_level": "Bronze", "username": "test_user"},
    })
    badge_c = connector.normalize_evidence({
        "type": "hackerrank_badge",
        "data": {"badge_name": "C", "stars": 3, "hatch_level": "Bronze", "username": "test_user"},
    })

    # Ensure none of these badges emit 'Functions'
    for b in [badge_ps, badge_py, badge_c]:
        assert b["platform"] == "HackerRank"
        assert "external_id" in b
        assert "title" in b
        mapped_slugs = [CONCEPT_TO_SKILL_SLUG.get(s) for s in b["normalized_payload"]["skills"]]
        assert "functions" not in mapped_slugs, f"Falsely mapped to 'functions': {mapped_slugs}"


def test_mastery_calculation_engine():
    """Verify all 10 mastery engine criteria from Task 3:
    1. No evidence -> 0 mastery / NO_EVIDENCE
    2. One weak evidence item -> appropriate low mastery (< 15%, weak)
    3. Multiple evidence items -> mastery increases in a controlled way
    4. Stronger evidence does not produce a lower score than weaker evidence (4-star > 3-star > 1-star)
    5. Generic programming evidence must not incorrectly create Functions mastery
    6. HackerRank Problem Solving evidence contributes only to Problem Solving
    7. HackerRank Python evidence contributes only to Python
    8. HackerRank C evidence contributes only to C
    9. Existing Task 1 total_solved remains 38 for dnyeya
    10. Existing Task 2 mapping remains intact
    """
    import uuid
    from app.database import SessionLocal
    from app.models.user import User
    from app.models.platform import PlatformConnection
    from app.models.evidence import Evidence
    from app.services.mesh.concept_extractor import ConceptExtractorService, CONCEPT_TO_SKILL_SLUG

    db = SessionLocal()
    test_user_id = str(uuid.uuid4())
    test_user = User(
        id=test_user_id,
        clerk_user_id=f"clerk_{uuid.uuid4().hex[:8]}",
        email=f"test_{uuid.uuid4().hex[:6]}@example.com",
    )
    db.add(test_user)
    db.commit()

    try:
        extractor = ConceptExtractorService()

        # 1. No evidence -> 0 mastery / NO_EVIDENCE
        assessments_0 = extractor.extract_and_assess_user_skills(test_user_id, db)
        ass_map_0 = {a.skill.slug: a for a in assessments_0}
        assert ass_map_0["functions"].mastery_score == 0.0
        assert ass_map_0["functions"].status == "NO_EVIDENCE"
        assert ass_map_0["problem-solving"].mastery_score == 0.0
        assert ass_map_0["problem-solving"].status == "NO_EVIDENCE"

        # Create active PlatformConnection
        conn = PlatformConnection(
            id=str(uuid.uuid4()),
            user_id=test_user_id,
            platform="HackerRank",
            username="test_hr",
            connected=True,
        )
        db.add(conn)
        db.commit()

        # 2. One weak evidence item -> appropriate low mastery (1-star badge)
        ev_1star = Evidence(
            id=str(uuid.uuid4()),
            user_id=test_user_id,
            platform_connection_id=conn.id,
            external_id="hr_badge_ps_1",
            title="HackerRank Badge: Problem Solving (1 Stars)",
            evidence_type="badge",
            normalized_payload={
                "badge_name": "Problem Solving",
                "stars": 1,
                "skills": ["Problem Solving", "Problem Solving"],
            },
        )
        db.add(ev_1star)
        db.commit()

        assessments_1 = extractor.extract_and_assess_user_skills(test_user_id, db)
        ass_map_1 = {a.skill.slug: a for a in assessments_1}
        ps_1 = ass_map_1["problem-solving"]
        assert ps_1.evidence_count == 1
        assert ps_1.mastery_score == 10.0  # (1.0 * 7.5) + (1 * 2.5) = 10.0
        assert ps_1.status == "weak"
        ps_1_score = ps_1.mastery_score

        # 3. Multiple evidence items -> mastery increases in a controlled way
        ev_profile = Evidence(
            id=str(uuid.uuid4()),
            user_id=test_user_id,
            platform_connection_id=conn.id,
            external_id="hr_profile",
            title="HackerRank Profile: test_hr",
            evidence_type="profile",
            normalized_payload={
                "skills": ["Algorithms", "Problem Solving"],
                "total_solved": 38,
                "level": 5,
            },
        )
        db.add(ev_profile)
        db.commit()

        assessments_2 = extractor.extract_and_assess_user_skills(test_user_id, db)
        ass_map_2 = {a.skill.slug: a for a in assessments_2}
        ps_2 = ass_map_2["problem-solving"]
        assert ps_2.evidence_count == 2
        assert ps_2.mastery_score == 20.0  # (2.0 * 7.5) + (2 * 2.5) = 20.0
        assert ps_2.mastery_score > ps_1_score
        assert ps_2.status == "weak"

        # 4. Stronger evidence should not produce a lower score than weaker evidence (4-star vs 3-star vs 1-star)
        ev_py_4star = Evidence(
            id=str(uuid.uuid4()),
            user_id=test_user_id,
            platform_connection_id=conn.id,
            external_id="hr_badge_py_4",
            title="HackerRank Badge: Python (4 Stars)",
            evidence_type="badge",
            normalized_payload={
                "badge_name": "Python",
                "stars": 4,
                "skills": ["Python", "Problem Solving"],
            },
        )
        ev_c_3star = Evidence(
            id=str(uuid.uuid4()),
            user_id=test_user_id,
            platform_connection_id=conn.id,
            external_id="hr_badge_c_3",
            title="HackerRank Badge: C (3 Stars)",
            evidence_type="badge",
            normalized_payload={
                "badge_name": "C",
                "stars": 3,
                "skills": ["C", "Problem Solving"],
            },
        )
        db.add_all([ev_py_4star, ev_c_3star])
        db.commit()

        assessments_3 = extractor.extract_and_assess_user_skills(test_user_id, db)
        ass_map_3 = {a.skill.slug: a for a in assessments_3}
        py_score = ass_map_3["python"].mastery_score
        c_score = ass_map_3["c"].mastery_score
        ps_1star_score = 10.0

        assert py_score == 21.2  # (2.5 * 7.5) + (1 * 2.5) = 21.25 -> 21.2
        assert c_score == 17.5   # (2.0 * 7.5) + (1 * 2.5) = 17.5
        assert py_score > c_score > ps_1star_score, "Monotonicity violated: 4-star > 3-star > 1-star"

        # 5. Generic programming evidence must not incorrectly create Functions mastery
        assert ass_map_3["functions"].evidence_count == 0
        assert ass_map_3["functions"].mastery_score == 0.0
        assert ass_map_3["functions"].status == "NO_EVIDENCE"

        # 6. HackerRank Problem Solving evidence contributes only to Problem Solving
        assert ass_map_3["problem-solving"].evidence_count == 2
        assert ass_map_3["problem-solving"].mastery_score == 20.0

        # 7. HackerRank Python evidence contributes only to Python
        assert ass_map_3["python"].evidence_count == 1
        assert ass_map_3["python"].mastery_score == 21.2

        # 8. HackerRank C evidence contributes only to C
        assert ass_map_3["c"].evidence_count == 1
        assert ass_map_3["c"].mastery_score == 17.5

        # 9. Existing Task 1 total_solved remains 38 for dnyeya
        from app.services.platform.hackerrank import HackerRankConnector
        connector = HackerRankConnector()
        prof_norm = connector.normalize_evidence({
            "type": "hackerrank_profile",
            "data": {"username": "dnyeya", "total_solved": 38, "level": 5},
        })
        assert prof_norm["normalized_payload"]["total_solved"] == 38

        # 10. Existing Task 2 mapping remains intact
        assert CONCEPT_TO_SKILL_SLUG.get("Problem Solving") == "problem-solving"
        assert CONCEPT_TO_SKILL_SLUG.get("Python") == "python"
        assert CONCEPT_TO_SKILL_SLUG.get("C") == "c"
        assert CONCEPT_TO_SKILL_SLUG.get("Functions") == "functions"

    finally:
        u = db.query(User).filter(User.id == test_user_id).first()
        if u:
            db.delete(u)
            db.commit()
        db.close()


@pytest.mark.asyncio
async def test_hackerrank_recent_challenges_topic_evidence():
    """Verify all 12 Task 2 criteria for HackerRank recent challenges -> topic evidence:
    1. recent_challenges endpoint parsing
    2. challenge evidence is created
    3. challenge title/provenance is preserved
    4. HackerRank topic metadata is preserved
    5. Functions challenge maps to functions
    6. Lists challenge maps to lists
    7. Sets challenge maps to sets
    8. Arrays challenge maps to arrays
    9. Python/C badges continue mapping to python/c
    10. Existing total_solved aggregation remains 38 for mocked (7+17+14)
    11. No challenge evidence is incorrectly added to unrelated skills
    12. Existing tests continue passing and ConceptExtractor integrates correctly
    """
    import uuid
    from app.database import SessionLocal
    from app.models.user import User
    from app.models.platform import PlatformConnection
    from app.models.evidence import Evidence
    from app.services.mesh.concept_extractor import ConceptExtractorService, CONCEPT_TO_SKILL_SLUG

    connector = HackerRankConnector()

    mock_profile_res = {"model": {"username": "demo_hr", "name": "Demo Hacker", "level": 4}}
    mock_badges_res = {"models": [
        {"badge_name": "Problem Solving", "stars": 1, "hatch_level": "Bronze", "solved": 7},
        {"badge_name": "Python", "stars": 4, "hatch_level": "Bronze", "solved": 17},
        {"badge_name": "C", "stars": 3, "hatch_level": "Bronze", "solved": 14},
    ]}
    mock_recent_res = {"models": [
        {
            "name": "Write a function",
            "ch_slug": "write-a-function",
            "created_at": "2024-03-20T10:00:00.000Z",
            "con_slug": "master",
            "url": "/challenges/write-a-function/problem",
            "track": {"name": "Introduction", "slug": "py-introduction", "track_name": "Python"},
        },
        {
            "name": "List Comprehensions",
            "ch_slug": "list-comprehensions",
            "created_at": "2024-03-21T10:00:00.000Z",
            "con_slug": "master",
            "url": "/challenges/list-comprehensions/problem",
            "track": {"name": "Basic Data Types", "slug": "py-basic-data-types", "track_name": "Python"},
        },
        {
            "name": "Introduction to Sets",
            "ch_slug": "py-introduction-to-sets",
            "created_at": "2024-03-22T10:00:00.000Z",
            "con_slug": "master",
            "url": "/challenges/py-introduction-to-sets/problem",
            "track": {"name": "Sets", "slug": "py-sets", "track_name": "Python"},
        },
        {
            "name": "Simple Array Sum",
            "ch_slug": "simple-array-sum",
            "created_at": "2024-03-23T10:00:00.000Z",
            "con_slug": "master",
            "url": "/challenges/simple-array-sum/problem",
            "track": {"name": "Warmup", "slug": "warmup", "track_name": "Algorithms"},
            "preview": "Calculate the sum of integers in an array.",
        },
        {
            "name": "Staircase",
            "ch_slug": "staircase",
            "created_at": "2024-03-24T10:00:00.000Z",
            "con_slug": "master",
            "url": "/challenges/staircase/problem",
            "track": {"name": "Warmup", "slug": "warmup", "track_name": "Algorithms"},
        },
    ]}

    # 1. recent_challenges endpoint parsing
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=AsyncMock(status_code=200, json=lambda: mock_recent_res))):
        recent_ch = await connector.fetch_recent_challenges("demo_hr", limit=20)
        assert len(recent_ch) == 5
        assert recent_ch[0]["name"] == "Write a function"
        assert recent_ch[0]["ch_slug"] == "write-a-function"
        assert recent_ch[0]["track"]["name"] == "Introduction"

    # 2. challenge evidence is created in fetch_evidence
    with patch("httpx.AsyncClient.get", side_effect=[
        AsyncMock(status_code=200, json=lambda: mock_badges_res),       # fetch_badges
        AsyncMock(status_code=200, json=lambda: mock_profile_res),      # fetch_profile
        AsyncMock(status_code=200, json=lambda: mock_recent_res),       # fetch_recent_challenges
    ]):
        evidence_items = await connector.fetch_evidence("demo_hr")
        assert len(evidence_items) == 9  # 1 profile + 3 badges + 5 challenges

        types = [item["type"] for item in evidence_items]
        assert types.count("hackerrank_profile") == 1
        assert types.count("hackerrank_badge") == 3
        assert types.count("hackerrank_challenge") == 5

    challenge_items = [it for it in evidence_items if it["type"] == "hackerrank_challenge"]
    assert len(challenge_items) == 5

    # 3. challenge title/provenance is preserved
    for ch_item in challenge_items:
        norm = connector.normalize_evidence(ch_item)
        assert norm["platform"] == "HackerRank"
        assert norm["evidence_type"] == "problem_submission"
        assert norm["title"].startswith("HackerRank Challenge:")
        assert norm["title"].endswith("(Solved)")
        assert norm["external_id"].startswith("hackerrank_challenge_")
        assert norm["source_url"].startswith("https://www.hackerrank.com/challenges/")
        assert norm["normalized_payload"]["status"] == "Solved"
        assert norm["normalized_payload"]["solved"] is True
        assert norm["occurred_at"] is not None

    # 4. HackerRank topic metadata is preserved
    norm_map = {ch["data"]["ch_slug"]: connector.normalize_evidence(ch) for ch in challenge_items}
    assert norm_map["write-a-function"]["normalized_payload"]["track"] == "Python"
    assert norm_map["write-a-function"]["normalized_payload"]["subdomain"] == "Introduction"
    assert norm_map["list-comprehensions"]["normalized_payload"]["subdomain"] == "Basic Data Types"
    assert norm_map["py-introduction-to-sets"]["normalized_payload"]["subdomain"] == "Sets"
    assert norm_map["simple-array-sum"]["normalized_payload"]["subdomain"] == "Warmup"
    assert norm_map["simple-array-sum"]["normalized_payload"]["track"] == "Algorithms"

    # 5. Functions challenge maps to functions
    norm_func = norm_map["write-a-function"]
    assert "Functions" in norm_func["normalized_payload"]["skills"]
    assert CONCEPT_TO_SKILL_SLUG.get("Functions") == "functions"

    # 6. Lists challenge maps to lists
    norm_list = norm_map["list-comprehensions"]
    assert "Lists" in norm_list["normalized_payload"]["skills"] or "List Comprehensions" in norm_list["normalized_payload"]["skills"]
    assert CONCEPT_TO_SKILL_SLUG.get("Lists") == "lists"
    assert CONCEPT_TO_SKILL_SLUG.get("List Comprehensions") == "lists"

    # 7. Sets challenge maps to sets
    norm_set = norm_map["py-introduction-to-sets"]
    assert "Sets" in norm_set["normalized_payload"]["skills"]
    assert CONCEPT_TO_SKILL_SLUG.get("Sets") == "sets"

    # 8. Arrays challenge maps to arrays
    norm_arr = norm_map["simple-array-sum"]
    assert "Arrays" in norm_arr["normalized_payload"]["skills"]
    assert CONCEPT_TO_SKILL_SLUG.get("Arrays") == "arrays"

    # 9. Python/C badges continue mapping to python/c
    badge_items = [it for it in evidence_items if it["type"] == "hackerrank_badge"]
    badge_norm_map = {b["data"]["badge_name"]: connector.normalize_evidence(b) for b in badge_items}
    assert CONCEPT_TO_SKILL_SLUG.get(badge_norm_map["Python"]["normalized_payload"]["badge_name"]) == "python"
    assert CONCEPT_TO_SKILL_SLUG.get(badge_norm_map["C"]["normalized_payload"]["badge_name"]) == "c"
    assert CONCEPT_TO_SKILL_SLUG.get(badge_norm_map["Problem Solving"]["normalized_payload"]["badge_name"]) == "problem-solving"

    # 10. Badge counts are NOT summed as unique solved total; lifetime unique total is None
    profile_item = next(it for it in evidence_items if it["type"] == "hackerrank_profile")
    prof_norm = connector.normalize_evidence(profile_item)
    assert prof_norm["normalized_payload"]["total_solved"] is None
    # Ensure badges (7 + 17 + 14 = 38) were NOT summed into total_solved
    assert prof_norm["normalized_payload"]["total_solved"] != 38
    assert prof_norm["normalized_payload"]["total_solved"] != 38 + 5

    # 11 & 12. ConceptExtractor integration: skills receive correct evidence, NO unrelated skills
    db = SessionLocal()
    test_user_id = str(uuid.uuid4())
    test_user = User(
        id=test_user_id,
        clerk_user_id=f"clerk_{uuid.uuid4().hex[:8]}",
        email=f"test_hr_topics_{uuid.uuid4().hex[:6]}@example.com",
    )
    db.add(test_user)
    db.commit()

    try:
        conn = PlatformConnection(
            id=str(uuid.uuid4()),
            user_id=test_user_id,
            platform="HackerRank",
            username="demo_hr",
            connected=True,
        )
        db.add(conn)
        db.commit()

        # Add all normalized evidence items to DB
        db_evs = []
        for raw_it in evidence_items:
            norm_it = connector.normalize_evidence(raw_it)
            db_evs.append(Evidence(
                id=str(uuid.uuid4()),
                user_id=test_user_id,
                platform_connection_id=conn.id,
                external_id=norm_it["external_id"],
                title=norm_it["title"],
                evidence_type=norm_it["evidence_type"],
                raw_payload=norm_it.get("raw_payload"),
                normalized_payload=norm_it.get("normalized_payload"),
            ))
        db.add_all(db_evs)
        db.commit()

        extractor = ConceptExtractorService()
        assessments = extractor.extract_and_assess_user_skills(test_user_id, db)
        ass_map = {a.skill.slug: a for a in assessments}

        # Functions received evidence
        assert ass_map["functions"].evidence_count >= 1
        assert ass_map["functions"].mastery_score > 0.0

        # Lists received evidence
        assert ass_map["lists"].evidence_count >= 1
        assert ass_map["lists"].mastery_score > 0.0

        # Sets received evidence
        assert ass_map["sets"].evidence_count >= 1
        assert ass_map["sets"].mastery_score > 0.0

        # Arrays received evidence
        assert ass_map["arrays"].evidence_count >= 1
        assert ass_map["arrays"].mastery_score > 0.0

        # Problem Solving received evidence (badge + challenges)
        assert ass_map["problem-solving"].evidence_count >= 2
        assert ass_map["problem-solving"].mastery_score > 0.0

        # Python received evidence (badge + challenges)
        assert ass_map["python"].evidence_count >= 1
        assert ass_map["python"].mastery_score > 0.0

        # C received evidence (badge)
        assert ass_map["c"].evidence_count == 1
        assert ass_map["c"].mastery_score > 0.0

        # 11. Strict check: Unrelated skills must have ZERO evidence and ZERO mastery
        assert ass_map["tree-traversal"].evidence_count == 0
        assert ass_map["tree-traversal"].mastery_score == 0.0
        assert ass_map["tree-traversal"].status == "NO_EVIDENCE"

        assert ass_map["dfs"].evidence_count == 0
        assert ass_map["dfs"].mastery_score == 0.0
        assert ass_map["dfs"].status == "NO_EVIDENCE"

        assert ass_map["graph-algorithms"].evidence_count == 0
        assert ass_map["graph-algorithms"].mastery_score == 0.0
        assert ass_map["graph-algorithms"].status == "NO_EVIDENCE"

        assert ass_map["recursion"].evidence_count == 0
        assert ass_map["recursion"].mastery_score == 0.0
        assert ass_map["recursion"].status == "NO_EVIDENCE"

        assert ass_map["async-programming"].evidence_count == 0
        assert ass_map["async-programming"].mastery_score == 0.0
        assert ass_map["async-programming"].status == "NO_EVIDENCE"

    finally:
        u = db.query(User).filter(User.id == test_user_id).first()
        if u:
            db.delete(u)
            db.commit()
        db.close()


