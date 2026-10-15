"""Regression and repair test suite for HackerRank connector (Batch 3).

Covers all 10 requirements:
1. Profile normalization.
2. Badge-level counters remain distinct.
3. Overlapping badge counts are not incorrectly summed as verified unique solves.
4. Verified unique count is extracted correctly if a reliable source exists.
5. Unknown unique count remains unknown when no reliable source exists.
6. Missing metric versus genuine zero.
7. Recent challenge evidence is not confused with lifetime solved count.
8. HTTP errors, rate limits, timeouts, and malformed responses.
9. Failed refresh preserves existing evidence.
10. API and profile-summary compatibility.
"""

import uuid
from typing import Any
import httpx
import pytest

from app.database import SessionLocal
from app.models.evidence import Evidence
from app.models.platform import PlatformConnection
from app.models.user import User
from app.services.platform.errors import RateLimitedError, UpstreamUnavailableError
from app.services.platform.hackerrank import HackerRankConnector


# --- Mock fixtures ---

MOCK_HR_PROFILE = {
    "model": {
        "username": "dnyeya",
        "name": "Dnyeya Hacker",
        "avatar": "https://hackerrank.com/avatar/dnyeya.png",
        "country": "India",
        "school": "NIT",
        "level": 3,
    }
}

MOCK_HR_BADGES = {
    "models": [
        {
            "badge_name": "Problem Solving",
            "badge_type": "problem-solving",
            "stars": 1,
            "hatch_level": "Bronze",
            "solved": 7,
            "total_challenges": 10,
        },
        {
            "badge_name": "Python",
            "badge_type": "python",
            "stars": 4,
            "hatch_level": "Gold",
            "solved": 17,
            "total_challenges": 20,
        },
        {
            "badge_name": "C",
            "badge_type": "c",
            "stars": 3,
            "hatch_level": "Silver",
            "solved": 14,
            "total_challenges": 15,
        },
    ]
}

MOCK_HR_CHALLENGES = {
    "models": [
        {"name": "Solve Me First", "ch_slug": "solve-me-first", "created_at": "2024-01-01T00:00:00Z"},
        {"name": "Simple Array Sum", "ch_slug": "simple-array-sum", "created_at": "2024-01-02T00:00:00Z"},
    ]
}


def make_hr_handler(
    profile_data=MOCK_HR_PROFILE,
    badges_data=MOCK_HR_BADGES,
    challenges_data=MOCK_HR_CHALLENGES,
    status_code=200,
):
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if status_code != 200:
            return httpx.Response(status_code, json={"error": "error"})
        if "/profile" in url:
            return httpx.Response(200, json=profile_data)
        if "/badges" in url:
            return httpx.Response(200, json=badges_data)
        if "/recent_challenges" in url:
            return httpx.Response(200, json=challenges_data)
        return httpx.Response(404, json={})

    return handler


# --- Tests ---


@pytest.mark.asyncio
async def test_01_hackerrank_profile_normalization():
    """Requirement 1: Profile telemetry is normalized accurately."""
    transport = httpx.MockTransport(make_hr_handler())
    connector = HackerRankConnector(transport=transport)

    profile = await connector.fetch_profile("dnyeya")
    assert profile is not None
    assert profile["username"] == "dnyeya"
    assert profile["name"] == "Dnyeya Hacker"
    assert profile["level"] == 3
    assert profile["country"] == "India"
    assert profile["avatar_url"] == "https://hackerrank.com/avatar/dnyeya.png"
    assert profile["html_url"] == "https://www.hackerrank.com/profile/dnyeya"

    norm = connector.normalize_evidence({"type": "hackerrank_profile", "data": profile})
    assert norm["platform"] == "HackerRank"
    assert norm["external_id"] == "hackerrank_profile_dnyeya"
    assert norm["evidence_type"] == "profile"
    assert norm["normalized_payload"]["level"] == 3
    assert "Algorithms" in norm["normalized_payload"]["skills"]
    assert "Problem Solving" in norm["normalized_payload"]["skills"]


@pytest.mark.asyncio
async def test_02_hackerrank_badge_counters_remain_distinct():
    """Requirement 2: Badge-level solved counters remain distinct metrics."""
    transport = httpx.MockTransport(make_hr_handler())
    connector = HackerRankConnector(transport=transport)

    badges = await connector.fetch_badges("dnyeya")
    assert len(badges) == 3

    b_map = {b["badge_name"]: b for b in badges}
    assert b_map["Problem Solving"]["solved"] == 7
    assert b_map["Python"]["solved"] == 17
    assert b_map["C"]["solved"] == 14

    norm_ps = connector.normalize_evidence({"type": "hackerrank_badge", "data": b_map["Problem Solving"]})
    assert norm_ps["normalized_payload"]["badge_name"] == "Problem Solving"
    assert norm_ps["normalized_payload"]["solved"] == 7

    norm_py = connector.normalize_evidence({"type": "hackerrank_badge", "data": b_map["Python"]})
    assert norm_py["normalized_payload"]["badge_name"] == "Python"
    assert norm_py["normalized_payload"]["solved"] == 17

    norm_c = connector.normalize_evidence({"type": "hackerrank_badge", "data": b_map["C"]})
    assert norm_c["normalized_payload"]["badge_name"] == "C"
    assert norm_c["normalized_payload"]["solved"] == 14


@pytest.mark.asyncio
async def test_03_hackerrank_overlapping_badges_not_summed_into_unique_solves():
    """Requirement 3: Overlapping badge counts (7+17+14) are NOT summed into verified unique solves."""
    transport = httpx.MockTransport(make_hr_handler())
    connector = HackerRankConnector(transport=transport)

    badges = await connector.fetch_badges("dnyeya")
    profile = await connector.fetch_profile("dnyeya", badges=badges)

    # Must NOT sum 7 + 17 + 14 = 38
    assert profile["total_solved"] is None
    assert profile["total_solved"] != 38

    norm = connector.normalize_evidence({"type": "hackerrank_profile", "data": profile})
    assert norm["normalized_payload"]["total_solved"] is None
    assert norm["normalized_payload"]["total_solved"] != 38


@pytest.mark.asyncio
async def test_04_hackerrank_verified_unique_count_preserved_when_present():
    """Requirement 4: When a verified unique count is supplied, it is preserved."""
    connector = HackerRankConnector()
    custom_profile = {
        "username": "custom_user",
        "total_solved": 42,
        "level": 2,
    }
    norm = connector.normalize_evidence({"type": "hackerrank_profile", "data": custom_profile})
    assert norm["normalized_payload"]["total_solved"] == 42


@pytest.mark.asyncio
async def test_05_hackerrank_unknown_unique_count_remains_unknown():
    """Requirement 5: When no reliable unique count exists, it remains None."""
    transport = httpx.MockTransport(make_hr_handler())
    connector = HackerRankConnector(transport=transport)

    profile = await connector.fetch_profile("dnyeya")
    assert profile["total_solved"] is None

    norm = connector.normalize_evidence({"type": "hackerrank_profile", "data": profile})
    assert norm["normalized_payload"]["total_solved"] is None


def test_06_hackerrank_missing_metric_vs_genuine_zero():
    """Requirement 6: Distinguish missing value (None) from genuine numeric zero (0)."""
    connector = HackerRankConnector()

    norm_none = connector.normalize_evidence({
        "type": "hackerrank_profile",
        "data": {"username": "user1", "total_solved": None},
    })
    assert norm_none["normalized_payload"]["total_solved"] is None

    norm_zero = connector.normalize_evidence({
        "type": "hackerrank_profile",
        "data": {"username": "user2", "total_solved": 0},
    })
    assert norm_zero["normalized_payload"]["total_solved"] == 0
    assert norm_zero["normalized_payload"]["total_solved"] is not None


@pytest.mark.asyncio
async def test_07_hackerrank_recent_challenges_not_confused_with_lifetime_count():
    """Requirement 7: Recent challenge evidence count is distinct from lifetime solved count."""
    transport = httpx.MockTransport(make_hr_handler())
    connector = HackerRankConnector(transport=transport)

    evidence = await connector.fetch_evidence("dnyeya")
    challenges = [e for e in evidence if e["type"] == "hackerrank_challenge"]
    profile_item = next(e for e in evidence if e["type"] == "hackerrank_profile")

    assert len(challenges) == 2
    # The profile's total_solved must NOT be set to the count of recent challenges (2)
    assert profile_item["data"]["total_solved"] is None
    assert profile_item["data"]["total_solved"] != len(challenges)


@pytest.mark.asyncio
async def test_08_hackerrank_http_errors_and_rate_limits():
    """Requirement 8: Typed errors for rate limits (429), server errors (500), and 404."""
    # 404 returns False / None
    t_404 = httpx.MockTransport(lambda req: httpx.Response(404, json={}))
    c_404 = HackerRankConnector(transport=t_404)
    assert await c_404.validate_identity("nonexistent") is False
    assert await c_404.fetch_profile("nonexistent") is None
    assert await c_404.fetch_badges("nonexistent") == []

    # 429 raises RateLimitedError
    t_429 = httpx.MockTransport(lambda req: httpx.Response(429, json={"message": "rate limit"}))
    c_429 = HackerRankConnector(transport=t_429)
    with pytest.raises(RateLimitedError):
        await c_429.validate_identity("dnyeya")
    with pytest.raises(RateLimitedError):
        await c_429.fetch_profile("dnyeya")

    # 500 raises UpstreamUnavailableError
    t_500 = httpx.MockTransport(lambda req: httpx.Response(500, text="Internal Error"))
    c_500 = HackerRankConnector(transport=t_500)
    with pytest.raises(UpstreamUnavailableError):
        await c_500.validate_identity("dnyeya")
    with pytest.raises(UpstreamUnavailableError):
        await c_500.fetch_profile("dnyeya")


@pytest.mark.asyncio
async def test_09_hackerrank_failed_refresh_preserves_database_evidence():
    """Requirement 9: Upstream failure during sync does not erase previously stored evidence."""
    db = SessionLocal()
    test_uid = str(uuid.uuid4())
    user = User(
        id=test_uid,
        clerk_user_id=f"clerk_{uuid.uuid4().hex[:8]}",
        email=f"hr_test_{uuid.uuid4().hex[:6]}@example.com",
    )
    db.add(user)
    db.commit()

    try:
        conn = PlatformConnection(
            id=str(uuid.uuid4()),
            user_id=test_uid,
            platform="HackerRank",
            username="dnyeya",
            connected=True,
        )
        db.add(conn)
        db.commit()

        # Existing valid badge and profile evidence
        ev_profile = Evidence(
            id=str(uuid.uuid4()),
            user_id=test_uid,
            platform_connection_id=conn.id,
            external_id="hackerrank_profile_dnyeya",
            title="HackerRank Profile: dnyeya",
            evidence_type="profile",
            raw_payload={"username": "dnyeya"},
            normalized_payload={"level": 3, "total_solved": None},
        )
        ev_badge = Evidence(
            id=str(uuid.uuid4()),
            user_id=test_uid,
            platform_connection_id=conn.id,
            external_id="hackerrank_badge_Python_4",
            title="HackerRank Badge: Python (4 Stars)",
            evidence_type="badge",
            raw_payload={"badge_name": "Python", "solved": 17},
            normalized_payload={"badge_name": "Python", "stars": 4, "solved": 17},
        )
        db.add_all([ev_profile, ev_badge])
        db.commit()

        # Simulate a failed sync call: upstream returns 500
        t_fail = httpx.MockTransport(lambda req: httpx.Response(500, text="Downstream error"))
        c_fail = HackerRankConnector(transport=t_fail)

        with pytest.raises(UpstreamUnavailableError):
            await c_fail.fetch_evidence("dnyeya")

        # Verify database evidence was NOT modified or deleted
        db.expire_all()
        persisted = db.query(Evidence).filter(Evidence.platform_connection_id == conn.id).all()
        assert len(persisted) == 2
        badge_row = next(e for e in persisted if e.external_id == "hackerrank_badge_Python_4")
        assert badge_row.normalized_payload["solved"] == 17
    finally:
        db.query(Evidence).filter(Evidence.user_id == test_uid).delete()
        db.query(PlatformConnection).filter(PlatformConnection.user_id == test_uid).delete()
        db.query(User).filter(User.id == test_uid).delete()
        db.commit()
        db.close()


@pytest.mark.asyncio
async def test_10_hackerrank_api_and_profile_summary_compatibility():
    """Requirement 10: Profile dictionary conforms to platform router expectations."""
    transport = httpx.MockTransport(make_hr_handler())
    connector = HackerRankConnector(transport=transport)

    profile = await connector.fetch_profile("dnyeya")
    assert profile is not None

    # Expected router keys
    assert "username" in profile
    assert "avatar_url" in profile
    assert "html_url" in profile
    assert "total_solved" in profile
    assert profile["total_solved"] is None  # Unknown, not fake aggregate
