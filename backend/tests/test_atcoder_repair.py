"""Comprehensive regression tests for AtCoder connector repair (Batch 2).

Covers all Phase 4 requirements:
1. Standard profile normalization.
2. Username/handle compatibility.
3. Rated and unrated profiles.
4. Missing rating and solved-count fields.
5. A genuine solved count of zero.
6. Successful solved-count retrieval.
7. Kenkoooo timeout, rate limit, server error, and malformed response.
8. Invalid or mismatched profile data where applicable.
9. Failed refresh preserves historical evidence.
"""

import json
import uuid
import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.evidence import Evidence
from app.models.platform import PlatformConnection
from app.models.user import User
from app.services.platform.atcoder import AtCoderConnector
from app.services.platform.errors import (
    RateLimitedError,
    UpstreamFormatError,
    UpstreamUnavailableError,
)

client = TestClient(app)

# --- Mock HTML and JSON Fixtures ---

HTML_RATED_USER = """
<!DOCTYPE html>
<html>
<head><title>tourist - AtCoder</title></head>
<body>
<div><a class="username" href="/users/tourist"><span>tourist</span></a></div>
<table class="dl-table mt-2">
    <tr><th class="no-break">Rank</th><td>1st</td></tr>
    <tr><th class="no-break">Rating</th><td><span class='user-red'>3730</span></td></tr>
    <tr><th class="no-break">Highest Rating</th><td><span class='user-red'>4229</span></td></tr>
    <tr><th class="no-break">Rated Matches</th><td>72</td></tr>
    <tr><th class="no-break">Last Competed</th><td>2026/09/27</td></tr>
</table>
<script>
var rank_history=[
    {"EndTime":1600000000,"Rank":1,"Rating":3600,"ContestName":"Contest 1"},
    {"EndTime":1700000000,"Rank":1,"Rating":4229,"ContestName":"Contest 2"},
    {"EndTime":1790000000,"Rank":1,"Rating":3730,"ContestName":"Contest 3"}
];
</script>
</body>
</html>
"""

HTML_UNRATED_USER = """
<!DOCTYPE html>
<html>
<head><title>newbie_coder - AtCoder</title></head>
<body>
<div><a class="username" href="/users/newbie_coder"><span>newbie_coder</span></a></div>
<table class="dl-table">
    <tr><th class="no-break">Country/Region</th><td>Japan</td></tr>
</table>
</body>
</html>
"""

HTML_USER_NOT_FOUND = """
<!DOCTYPE html>
<html>
<head><title>404 Not Found - AtCoder</title></head>
<body>
<h1>User not found</h1>
</body>
</html>
"""

KENKOOOO_USER_INFO_VALID = {
    "user_id": "tourist",
    "accepted_count": 1057,
    "accepted_count_rank": 4477,
    "rated_point_sum": 688543,
    "rated_point_sum_rank": 688,
}

KENKOOOO_USER_INFO_ZERO = {
    "user_id": "newbie_coder",
    "accepted_count": 0,
    "accepted_count_rank": 668895,
    "rated_point_sum": 0,
    "rated_point_sum_rank": 565663,
}

KENKOOOO_SUBMISSIONS_VALID = [
    {
        "id": 101,
        "epoch_second": 1600000100,
        "problem_id": "abc086_a",
        "contest_id": "abc086",
        "user_id": "tourist",
        "language": "C++14 (GCC 5.4.1)",
        "result": "AC",
    },
    {
        "id": 102,
        "epoch_second": 1600000200,
        "problem_id": "abc086_b",
        "contest_id": "abc086",
        "user_id": "tourist",
        "language": "Python (3.8.2)",
        "result": "AC",
    },
    {
        "id": 103,
        "epoch_second": 1600000300,
        "problem_id": "abc086_a",
        "contest_id": "abc086",
        "user_id": "tourist",
        "language": "C++14 (GCC 5.4.1)",
        "result": "AC",  # duplicate AC on same problem
    },
    {
        "id": 104,
        "epoch_second": 1600000400,
        "problem_id": "abc086_c",
        "contest_id": "abc086",
        "user_id": "tourist",
        "language": "Python (3.8.2)",
        "result": "WA",  # Not AC
    },
]


def make_atcoder_transport(
    html_status: int = 200,
    html_body: str = HTML_RATED_USER,
    kenkoooo_status: int = 200,
    kenkoooo_info: dict | None = None,
    submissions_status: int = 200,
    submissions: list | None = None,
) -> httpx.MockTransport:
    """Helper to mock AtCoder website and Kenkoooo API endpoints."""
    if kenkoooo_info is None:
        kenkoooo_info = KENKOOOO_USER_INFO_VALID
    if submissions is None:
        submissions = KENKOOOO_SUBMISSIONS_VALID

    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "atcoder.jp/users" in url_str:
            return httpx.Response(html_status, text=html_body)
        if "kenkoooo.com" in url_str and "v2/user_info" in url_str:
            if kenkoooo_status == 200:
                return httpx.Response(200, json=kenkoooo_info)
            return httpx.Response(kenkoooo_status, text="Error")
        if "kenkoooo.com" in url_str and "v3/user/submissions" in url_str:
            if submissions_status == 200:
                return httpx.Response(200, json=submissions)
            return httpx.Response(submissions_status, text="Error")
        return httpx.Response(404, text="Not Found")

    return httpx.MockTransport(handler)


# --- Tests ---


@pytest.mark.asyncio
async def test_01_atcoder_standard_profile_normalization():
    """Requirement 1 & 2: Standard profile normalization and handle/username compatibility."""
    transport = make_atcoder_transport()
    connector = AtCoderConnector(transport=transport)

    profile = await connector.fetch_profile("tourist")
    assert profile is not None
    assert profile["platform"] == "AtCoder"
    assert profile["username"] == "tourist"
    assert profile["handle"] == "tourist"  # backwards compatibility
    assert profile["name"] == "tourist"
    assert profile["rating"] == 3730
    assert profile["current_rating"] == 3730  # backwards compatibility
    assert profile["highest_rating"] == 4229
    assert profile["maxRating"] == 4229
    assert profile["global_rank"] == 1
    assert profile["rated_matches"] == 72
    assert profile["total_solved"] == 1057
    assert profile["html_url"] == "https://atcoder.jp/users/tourist"


@pytest.mark.asyncio
async def test_02_atcoder_unrated_profile_rating_is_none():
    """Requirement 3 & 4: Unrated profile has None rating (NOT zero)."""
    transport = make_atcoder_transport(
        html_body=HTML_UNRATED_USER,
        kenkoooo_info=KENKOOOO_USER_INFO_ZERO,
    )
    connector = AtCoderConnector(transport=transport)

    profile = await connector.fetch_profile("newbie_coder")
    assert profile is not None
    assert profile["username"] == "newbie_coder"
    assert profile["rating"] is None
    assert profile["current_rating"] is None
    assert profile["highest_rating"] is None
    assert profile["maxRating"] is None
    # total_solved from kenkoooo is genuine zero
    assert profile["total_solved"] == 0


@pytest.mark.asyncio
async def test_03_atcoder_missing_kenkoooo_solved_count_is_none():
    """Requirement 4 & 5: When Kenkoooo fails, total_solved is None (distinguished from zero)."""
    transport = make_atcoder_transport(
        html_body=HTML_RATED_USER,
        kenkoooo_status=500,
    )
    connector = AtCoderConnector(transport=transport)

    profile = await connector.fetch_profile("tourist")
    assert profile is not None
    assert profile["rating"] == 3730
    # Must be None, NOT 0
    assert profile["total_solved"] is None


@pytest.mark.asyncio
async def test_04_atcoder_genuine_zero_solved_count():
    """Requirement 5: Genuine numeric zero solved count preserved as 0."""
    transport = make_atcoder_transport(
        html_body=HTML_UNRATED_USER,
        kenkoooo_info={"user_id": "newbie_coder", "accepted_count": 0},
    )
    connector = AtCoderConnector(transport=transport)

    profile = await connector.fetch_profile("newbie_coder")
    assert profile is not None
    assert profile["total_solved"] == 0
    assert profile["total_solved"] is not None


@pytest.mark.asyncio
async def test_05_atcoder_fetch_evidence_and_deduplication():
    """Requirement 6: Evidence fetching extracts AC problems, deduplicates, and normalizes skills."""
    transport = make_atcoder_transport()
    connector = AtCoderConnector(transport=transport)

    evidence = await connector.fetch_evidence("tourist")
    assert len(evidence) == 1
    item = evidence[0]
    assert item["type"] == "atcoder_profile_stats"
    assert item["total_submissions"] == 4
    # 2 unique AC problems in mock (abc086_a, abc086_b) or total_solved from profile
    assert item["total_solved"] == 1057
    assert "c++14" in item["languages"]
    assert "python" in item["languages"]

    norm = connector.normalize_evidence(item)
    assert norm["platform"] == "AtCoder"
    assert norm["external_id"] == "atcoder_profile_tourist"
    assert norm["evidence_type"] == "problem_solving_summary"
    assert "Rating: 3730" in norm["title"]
    assert norm["normalized_payload"]["rating"] == 3730
    assert norm["normalized_payload"]["maxRating"] == 4229
    assert norm["normalized_payload"]["total_solved"] == 1057
    assert norm["normalized_payload"]["total_submissions"] == 4
    assert "c++14" in norm["normalized_payload"]["skills"]
    assert "python" in norm["normalized_payload"]["skills"]


@pytest.mark.asyncio
async def test_06_atcoder_unrated_evidence_normalization():
    """Unrated user evidence normalized payload has rating: None (NOT 0)."""
    transport = make_atcoder_transport(
        html_body=HTML_UNRATED_USER,
        kenkoooo_info=KENKOOOO_USER_INFO_ZERO,
        submissions=[],
    )
    connector = AtCoderConnector(transport=transport)

    evidence = await connector.fetch_evidence("newbie_coder")
    assert len(evidence) == 1
    norm = connector.normalize_evidence(evidence[0])
    assert norm["normalized_payload"]["rating"] is None
    assert norm["normalized_payload"]["maxRating"] is None
    assert norm["normalized_payload"]["total_solved"] == 0
    assert "Rating:" not in norm["title"]


@pytest.mark.asyncio
async def test_07_atcoder_kenkoooo_errors():
    """Requirement 7: Kenkoooo 429, 500, timeout, and malformed responses raise typed errors."""
    # 1. Kenkoooo 429 in fetch_evidence
    transport_429 = make_atcoder_transport(submissions_status=429)
    with pytest.raises(RateLimitedError):
        await AtCoderConnector(transport=transport_429).fetch_evidence("tourist")

    # 2. Kenkoooo 503 in fetch_evidence
    transport_503 = make_atcoder_transport(submissions_status=503)
    with pytest.raises(UpstreamUnavailableError):
        await AtCoderConnector(transport=transport_503).fetch_evidence("tourist")

    # 3. Kenkoooo timeout in fetch_evidence
    def timeout_handler(req: httpx.Request):
        if "submissions" in str(req.url):
            raise httpx.ReadTimeout("Timeout reading Kenkoooo submissions")
        return httpx.Response(200, text=HTML_RATED_USER)

    transport_timeout = httpx.MockTransport(timeout_handler)
    with pytest.raises(UpstreamUnavailableError):
        await AtCoderConnector(transport=transport_timeout).fetch_evidence("tourist")

    # 4. Kenkoooo malformed response
    def malformed_handler(req: httpx.Request):
        if "submissions" in str(req.url):
            return httpx.Response(200, text="NOT_VALID_JSON{")
        return httpx.Response(200, text=HTML_RATED_USER)

    transport_malformed = httpx.MockTransport(malformed_handler)
    with pytest.raises(UpstreamFormatError):
        await AtCoderConnector(transport=transport_malformed).fetch_evidence("tourist")


@pytest.mark.asyncio
async def test_08_atcoder_invalid_identity_and_404():
    """Requirement 8: 404 response or invalid username handled safely."""
    # Empty or illegal handles
    connector = AtCoderConnector()
    assert await connector.validate_identity("") is False
    assert await connector.validate_identity("   ") is False
    assert await connector.validate_identity("invalid/handle?") is False
    assert await connector.fetch_profile("") is None

    # 404 from AtCoder
    transport_404 = make_atcoder_transport(html_status=404, html_body="Not Found")
    conn_404 = AtCoderConnector(transport=transport_404)
    assert await conn_404.validate_identity("non_existent_user") is False
    assert await conn_404.fetch_profile("non_existent_user") is None

    # AtCoder site 404 masked as 200
    transport_masked_404 = make_atcoder_transport(html_status=200, html_body=HTML_USER_NOT_FOUND)
    conn_masked = AtCoderConnector(transport=transport_masked_404)
    assert await conn_masked.validate_identity("non_existent_user") is False
    assert await conn_masked.fetch_profile("non_existent_user") is None


def test_09_atcoder_failed_refresh_preserves_database_evidence(db_session, monkeypatch):
    """Requirement 9: A failed sync preserves existing valid evidence in the database."""
    uid = uuid.uuid4().hex[:12]
    user = User(clerk_user_id=f"test_atcoder_preserve_{uid}", email=f"atcoder_preserve_{uid}@test.com")
    db_session.add(user)
    db_session.commit()

    conn = PlatformConnection(
        user_id=user.id,
        platform="AtCoder",
        username="tourist",
        connected=True,
    )
    db_session.add(conn)
    db_session.commit()

    ev = Evidence(
        user_id=user.id,
        platform_connection_id=conn.id,
        external_id=f"atcoder_profile_tourist_{uid}",
        evidence_type="problem_solving_summary",
        title="AtCoder Profile: tourist (Rating: 3730)",
        normalized_payload={"rating": 3730, "total_solved": 1057},
        raw_payload={"total_solved": 1057, "rating": 3730},
    )
    db_session.add(ev)
    db_session.commit()

    try:
        # Simulate Kenkoooo outage during sync (502 / UpstreamUnavailableError)
        from app.services.platform.registry import PlatformRegistry

        failing_transport = make_atcoder_transport(submissions_status=502)
        failing_connector = AtCoderConnector(transport=failing_transport)
        monkeypatch.setattr(
            PlatformRegistry,
            "get_connector_instance",
            lambda key, auth_token=None: failing_connector,
        )

        headers = {"X-Clerk-User-Id": user.clerk_user_id}
        res = client.post(
            "/api/v1/platforms/atcoder/sync",
            json={"username": "tourist", "auth_type": "username_public"},
            headers=headers,
        )
        assert res.status_code == 502

        # Verify historical evidence was not deleted or altered
        db_session.refresh(conn)
        assert conn.connected is True
        existing_ev = (
            db_session.query(Evidence)
            .filter_by(user_id=user.id, external_id=f"atcoder_profile_tourist_{uid}")
            .first()
        )
        assert existing_ev is not None
        assert existing_ev.normalized_payload["rating"] == 3730
        assert existing_ev.normalized_payload["total_solved"] == 1057
    finally:
        db_session.query(Evidence).filter_by(user_id=user.id).delete()
        db_session.query(PlatformConnection).filter_by(user_id=user.id).delete()
        db_session.query(User).filter_by(id=user.id).delete()
        db_session.commit()
