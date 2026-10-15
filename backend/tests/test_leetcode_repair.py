"""Comprehensive regression tests for LeetCode connector repair (Batch 1).

Covers all Phase 4 requirements:
1. Successful profile response containing contest data.
2. Correct extraction of contest rating, global contest ranking, and attended-contest count.
3. Existing total/easy/medium/hard solved counts remain unchanged.
4. Null contest-ranking object.
5. Missing optional contest fields.
6. A user who has not participated in contests.
7. Numeric zero versus missing/null values.
8. Malformed GraphQL response.
9. GraphQL errors or HTTP 4xx/5xx.
10. Timeout handling.
11. Existing profile metrics continue to normalize correctly.
12. Connector does not confuse profile ranking with contest ranking.
"""

from unittest.mock import AsyncMock, patch
import pytest
import httpx

from app.services.platform.leetcode import LeetCodeConnector


# --- Fixtures ---

MOCK_GQL_FULL = {
    "data": {
        "matchedUser": {
            "username": "nilesh_1001",
            "profile": {
                "realName": "Nilesh Dev",
                "userAvatar": "https://assets.leetcode.com/avatar/nilesh.png",
                "ranking": 465190,
            },
            "submitStatsGlobal": {
                "acSubmissionNum": [
                    {"difficulty": "All", "count": 321},
                    {"difficulty": "Easy", "count": 128},
                    {"difficulty": "Medium", "count": 160},
                    {"difficulty": "Hard", "count": 33},
                ]
            },
        },
        "userContestRanking": {
            "attendedContestsCount": 16,
            "rating": 1605.16734,
            "globalRanking": 208151,
            "totalParticipants": 500000,
            "topPercentage": 35.5,
        },
    }
}

MOCK_GQL_NO_CONTEST = {
    "data": {
        "matchedUser": {
            "username": "coder_new",
            "profile": {
                "realName": "New Coder",
                "userAvatar": None,
                "ranking": 850000,
            },
            "submitStatsGlobal": {
                "acSubmissionNum": [
                    {"difficulty": "All", "count": 50},
                    {"difficulty": "Easy", "count": 40},
                    {"difficulty": "Medium", "count": 10},
                    {"difficulty": "Hard", "count": 0},
                ]
            },
        },
        "userContestRanking": None,
    }
}

MOCK_GQL_ZERO_RATING = {
    "data": {
        "matchedUser": {
            "username": "zero_user",
            "profile": {
                "realName": "Zero Rater",
                "userAvatar": None,
                "ranking": 999999,
            },
            "submitStatsGlobal": {
                "acSubmissionNum": [
                    {"difficulty": "All", "count": 10},
                    {"difficulty": "Easy", "count": 10},
                    {"difficulty": "Medium", "count": 0},
                    {"difficulty": "Hard", "count": 0},
                ]
            },
        },
        "userContestRanking": {
            "attendedContestsCount": 1,
            "rating": 0.0,
            "globalRanking": 500000,
            "totalParticipants": 500000,
            "topPercentage": 100.0,
        },
    }
}

MOCK_GQL_PARTIAL_CONTEST = {
    "data": {
        "matchedUser": {
            "username": "partial_contest",
            "profile": {
                "realName": "Partial",
                "userAvatar": None,
                "ranking": 300000,
            },
            "submitStatsGlobal": {
                "acSubmissionNum": [
                    {"difficulty": "All", "count": 20},
                    {"difficulty": "Easy", "count": 10},
                    {"difficulty": "Medium", "count": 10},
                    {"difficulty": "Hard", "count": 0},
                ]
            },
        },
        "userContestRanking": {
            "rating": 1542.8,
            # globalRanking, attendedContestsCount, topPercentage omitted upstream
        },
    }
}


# --- Test Cases ---

@pytest.mark.asyncio
async def test_1_and_2_and_3_leetcode_profile_with_contest_metrics():
    """Cases 1, 2, 3: Full contest data parsed accurately, solved counts preserved."""
    connector = LeetCodeConnector()
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=AsyncMock(status_code=200, json=lambda: MOCK_GQL_FULL))):
        prof = await connector.fetch_profile("nilesh_1001")

        assert prof is not None
        # Case 1 & 2: Contest metrics
        assert prof["contest_rating"] == 1605.17
        assert prof["rating"] == 1605.17
        assert prof["contest_ranking"] == 208151
        assert prof["contest_attended"] == 16
        assert prof["contest_top_percentage"] == 35.5

        # Case 3: Solved counts preserved
        assert prof["total_solved"] == 321
        assert prof["easy_solved"] == 128
        assert prof["medium_solved"] == 160
        assert prof["hard_solved"] == 33

        # Case 12 check: Ordinary profile ranking distinct from contest ranking
        assert prof["ranking"] == 465190
        assert prof["contest_ranking"] == 208151
        assert prof["ranking"] != prof["contest_ranking"]


@pytest.mark.asyncio
async def test_4_and_6_leetcode_null_contest_ranking():
    """Cases 4 & 6: Null contest ranking object / user who has not participated."""
    connector = LeetCodeConnector()
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=AsyncMock(status_code=200, json=lambda: MOCK_GQL_NO_CONTEST))):
        prof = await connector.fetch_profile("coder_new")

        assert prof is not None
        # Must be None, never 0
        assert prof["contest_rating"] is None
        assert prof["rating"] is None
        assert prof["contest_ranking"] is None
        assert prof["contest_attended"] is None
        assert prof["contest_top_percentage"] is None

        # Solved counts still work
        assert prof["total_solved"] == 50
        assert prof["easy_solved"] == 40
        assert prof["ranking"] == 850000


@pytest.mark.asyncio
async def test_5_leetcode_missing_optional_contest_fields():
    """Case 5: Partial contest response with missing optional fields."""
    connector = LeetCodeConnector()
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=AsyncMock(status_code=200, json=lambda: MOCK_GQL_PARTIAL_CONTEST))):
        prof = await connector.fetch_profile("partial_contest")

        assert prof is not None
        assert prof["contest_rating"] == 1542.8
        assert prof["contest_ranking"] is None
        assert prof["contest_attended"] is None
        assert prof["contest_top_percentage"] is None
        assert prof["total_solved"] == 20


@pytest.mark.asyncio
async def test_7_leetcode_zero_vs_null():
    """Case 7: Numeric zero rating is preserved as 0.0, distinct from None."""
    connector = LeetCodeConnector()
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=AsyncMock(status_code=200, json=lambda: MOCK_GQL_ZERO_RATING))):
        prof = await connector.fetch_profile("zero_user")

        assert prof is not None
        assert prof["contest_rating"] == 0.0
        assert prof["rating"] == 0.0
        assert prof["contest_rating"] is not None
        assert prof["contest_attended"] == 1


@pytest.mark.asyncio
async def test_8_leetcode_malformed_graphql_response():
    """Case 8: Malformed GraphQL response handled safely without uncaught crash."""
    connector = LeetCodeConnector()
    bad_responses = [
        {"data": None},
        {"errors": [{"message": "User not found"}]},
        {"data": {"matchedUser": None}},
        {},
    ]
    for bad in bad_responses:
        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=AsyncMock(status_code=200, json=lambda: bad))):
            assert await connector.fetch_profile("bad") is None


@pytest.mark.asyncio
async def test_9_leetcode_graphql_error_or_http_5xx():
    """Case 9: HTTP 4xx or 5xx returns None."""
    connector = LeetCodeConnector()
    for code in [400, 404, 500, 502]:
        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=AsyncMock(status_code=code, json=lambda: {}))):
            assert await connector.fetch_profile("server_err") is None


@pytest.mark.asyncio
async def test_10_leetcode_timeout_handling():
    """Case 10: Timeout exception handled gracefully."""
    connector = LeetCodeConnector()
    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Timeout")):
        assert await connector.fetch_profile("timeout_user") is None
        assert await connector.validate_identity("timeout_user") is False
        assert await connector.fetch_recent_submissions("timeout_user") == []
        assert await connector.fetch_skill_stats("timeout_user") == []


@pytest.mark.asyncio
async def test_11_leetcode_profile_metrics_normalization():
    """Case 11: Normalization produces schema-compliant payload with contest fields."""
    connector = LeetCodeConnector()
    profile = {
        "platform": "LeetCode",
        "username": "nilesh_1001",
        "name": "Nilesh Dev",
        "avatar_url": None,
        "html_url": "https://leetcode.com/nilesh_1001/",
        "ranking": 465190,
        "total_solved": 321,
        "easy_solved": 128,
        "medium_solved": 160,
        "hard_solved": 33,
        "contest_rating": 1605.17,
        "contest_ranking": 208151,
        "contest_attended": 16,
        "contest_top_percentage": 35.5,
        "rating": 1605.17,
    }
    raw_item = {"type": "leetcode_profile_stats", "data": profile}
    norm = connector.normalize_evidence(raw_item)

    assert norm["platform"] == "LeetCode"
    assert norm["evidence_type"] == "problem_solving_summary"
    assert norm["external_id"] == "leetcode_profile_nilesh_1001"
    payload = norm["normalized_payload"]
    assert payload["total_solved"] == 321
    assert payload["ranking"] == 465190
    assert payload["contest_rating"] == 1605.17
    assert payload["contest_ranking"] == 208151
    assert payload["contest_attended"] == 16
    assert payload["contest_top_percentage"] == 35.5
    assert "Algorithms" in payload["skills"]
    assert "Problem Solving" in payload["skills"]


@pytest.mark.asyncio
async def test_12_leetcode_profile_ranking_vs_contest_ranking():
    """Case 12: Distinct ranking semantics (profile ranking vs global contest ranking)."""
    connector = LeetCodeConnector()
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=AsyncMock(status_code=200, json=lambda: MOCK_GQL_FULL))):
        prof = await connector.fetch_profile("nilesh_1001")
        assert prof["ranking"] == 465190  # Profile rank
        assert prof["contest_ranking"] == 208151  # Contest rank
        assert prof["ranking"] != prof["contest_ranking"]

        norm = connector.normalize_evidence({"type": "leetcode_profile_stats", "data": prof})
        assert norm["normalized_payload"]["ranking"] == 465190
        assert norm["normalized_payload"]["contest_ranking"] == 208151
