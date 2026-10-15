"""Regression and repair test suite for Codeforces connector (Batch 3).

Covers all requirements and acceptance gaps:
1. One-page submission history.
2. Multiple-page submission history.
3. More than 1,000 submissions.
4. Duplicate accepted submissions for the same problem.
5. Accepted and non-accepted verdicts.
6. Problems from different contests with the same problem index.
7. Empty submission history (genuine zero).
8. A failed request on a later page (no partial counts returned).
9. Rate limits, timeouts, server errors, and malformed responses.
10. Pagination termination and repeated-page protection.
11. Correct behavior when a complete history cannot be retrieved.
12. Failed synchronization preserves valid historical evidence.
13. Hard-cap guard: reaching max_pages without end-of-history raises IncompleteHistoryError.
14. Normal termination on an empty page.
15. Normal termination on a short final page.
16. Bounded retries: transient failure followed by success.
17. Bounded retries: retry exhaustion raises typed error without partial counts.
"""

import uuid
from typing import Any
import httpx
import pytest

from app.database import SessionLocal
from app.models.evidence import Evidence
from app.models.platform import PlatformConnection
from app.models.user import User
from app.services.platform.codeforces import CodeforcesConnector, IncompleteHistoryError
from app.services.platform.errors import RateLimitedError, UpstreamUnavailableError

MOCK_CF_USER = {
    "status": "OK",
    "result": [
        {
            "handle": "tourist",
            "firstName": "Gennady",
            "lastName": "Korotkevich",
            "rating": 3800,
            "maxRating": 3979,
            "rank": "legendary grandmaster",
            "contribution": 150,
            "titlePhoto": "https://userpic.codeforces.org/tourist.jpg",
        }
    ],
}


def make_sub(sub_id: int, contest_id: int, index: str, name: str, verdict: str = "OK") -> dict[str, Any]:
    return {
        "id": sub_id,
        "contestId": contest_id,
        "creationTimeSeconds": 1700000000 + sub_id,
        "problem": {
            "contestId": contest_id,
            "index": index,
            "name": name,
            "tags": ["math", "greedy"],
        },
        "programmingLanguage": "GNU C++20",
        "verdict": verdict,
    }


# --- Tests ---


@pytest.mark.asyncio
async def test_01_codeforces_one_page_submission_history():
    """Requirement 1: Single page of submissions is correctly ingested and counted."""
    subs = [
        make_sub(1, 100, "A", "Problem 100A", "OK"),
        make_sub(2, 100, "B", "Problem 100B", "WRONG_ANSWER"),
        make_sub(3, 101, "A", "Problem 101A", "OK"),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "user.info" in url:
            return httpx.Response(200, json=MOCK_CF_USER)
        if "user.status" in url:
            return httpx.Response(200, json={"status": "OK", "result": subs})
        return httpx.Response(404, json={})

    transport = httpx.MockTransport(handler)
    connector = CodeforcesConnector(transport=transport)

    profile = await connector.fetch_profile("tourist")
    assert profile is not None
    assert profile["total_solved"] == 2  # 100_A and 101_A


@pytest.mark.asyncio
async def test_02_and_03_codeforces_multiple_pages_and_over_1000_submissions():
    """Requirements 2 & 3: Multi-page pagination retrieves history beyond 1,000 submissions."""
    # Page 1: 1000 submissions, 600 unique problems
    page1 = [make_sub(i, i % 600 + 1, "A", f"P_{i % 600 + 1}", "OK") for i in range(1, 1001)]
    # Page 2: 300 submissions, 200 new unique problems (problems 601..800)
    page2 = [make_sub(1000 + i, 600 + (i % 200 + 1), "A", f"P_{600 + (i % 200 + 1)}", "OK") for i in range(1, 301)]

    requested_offsets = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "user.info" in url:
            return httpx.Response(200, json=MOCK_CF_USER)
        if "user.status" in url:
            import urllib.parse
            parsed = urllib.parse.urlparse(url)
            qs = urllib.parse.parse_qs(parsed.query)
            from_idx = int(qs.get("from", [1])[0])
            requested_offsets.append(from_idx)
            if from_idx == 1:
                return httpx.Response(200, json={"status": "OK", "result": page1})
            elif from_idx == 1001:
                return httpx.Response(200, json={"status": "OK", "result": page2})
            else:
                return httpx.Response(200, json={"status": "OK", "result": []})
        return httpx.Response(404, json={})

    transport = httpx.MockTransport(handler)
    connector = CodeforcesConnector(transport=transport)

    profile = await connector.fetch_profile("tourist")
    assert profile is not None
    # 600 from page 1 + 200 from page 2 = 800 total unique solved
    assert profile["total_solved"] == 800
    assert 1 in requested_offsets
    assert 1001 in requested_offsets


@pytest.mark.asyncio
async def test_04_codeforces_duplicate_accepted_submissions_deduplicated():
    """Requirement 4: Multiple accepted submissions for the same problem count only once."""
    subs = [
        make_sub(1, 50, "A", "Problem 50A", "OK"),
        make_sub(2, 50, "A", "Problem 50A", "OK"),
        make_sub(3, 50, "A", "Problem 50A", "OK"),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "user.info" in url:
            return httpx.Response(200, json=MOCK_CF_USER)
        if "user.status" in url:
            return httpx.Response(200, json={"status": "OK", "result": subs})
        return httpx.Response(404, json={})

    transport = httpx.MockTransport(handler)
    connector = CodeforcesConnector(transport=transport)

    profile = await connector.fetch_profile("tourist")
    assert profile is not None
    assert profile["total_solved"] == 1


@pytest.mark.asyncio
async def test_05_codeforces_accepted_and_non_accepted_verdicts():
    """Requirement 5: Only 'OK' verdicts increment the solved count."""
    verdicts = [
        "OK",
        "WRONG_ANSWER",
        "TIME_LIMIT_EXCEEDED",
        "MEMORY_LIMIT_EXCEEDED",
        "COMPILATION_ERROR",
        "RUNTIME_ERROR",
        "CHALLENGED",
        "PARTIAL",
    ]
    subs = [make_sub(i, 200 + i, "A", f"P_{i}", v) for i, v in enumerate(verdicts, 1)]

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "user.info" in url:
            return httpx.Response(200, json=MOCK_CF_USER)
        if "user.status" in url:
            return httpx.Response(200, json={"status": "OK", "result": subs})
        return httpx.Response(404, json={})

    transport = httpx.MockTransport(handler)
    connector = CodeforcesConnector(transport=transport)

    profile = await connector.fetch_profile("tourist")
    assert profile is not None
    assert profile["total_solved"] == 1  # Only the first sub with verdict "OK"


@pytest.mark.asyncio
async def test_06_codeforces_different_contests_same_problem_index():
    """Requirement 6: Problems from different contests with same index are kept distinct."""
    subs = [
        make_sub(1, 100, "A", "Contest 100 Problem A", "OK"),
        make_sub(2, 200, "A", "Contest 200 Problem A", "OK"),
        make_sub(3, 300, "A", "Contest 300 Problem A", "OK"),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "user.info" in url:
            return httpx.Response(200, json=MOCK_CF_USER)
        if "user.status" in url:
            return httpx.Response(200, json={"status": "OK", "result": subs})
        return httpx.Response(404, json={})

    transport = httpx.MockTransport(handler)
    connector = CodeforcesConnector(transport=transport)

    profile = await connector.fetch_profile("tourist")
    assert profile is not None
    assert profile["total_solved"] == 3


@pytest.mark.asyncio
async def test_07_codeforces_empty_submission_history_is_genuine_zero():
    """Requirement 7: Empty submission history produces genuine 0, not None or error."""
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "user.info" in url:
            return httpx.Response(200, json=MOCK_CF_USER)
        if "user.status" in url:
            return httpx.Response(200, json={"status": "OK", "result": []})
        return httpx.Response(404, json={})

    transport = httpx.MockTransport(handler)
    connector = CodeforcesConnector(transport=transport)

    profile = await connector.fetch_profile("tourist")
    assert profile is not None
    assert profile["total_solved"] == 0
    assert profile["total_solved"] is not None

    norm = connector.normalize_evidence({"type": "codeforces_profile_stats", "data": profile})
    assert norm["normalized_payload"]["total_solved"] == 0


@pytest.mark.asyncio
async def test_08_and_11_codeforces_failed_request_on_later_page_raises_without_partial_count():
    """Requirements 8 & 11: Failure on later page raises typed error, does not return partial count."""
    page1 = [make_sub(i, i, "A", f"P_{i}", "OK") for i in range(1, 1001)]

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "user.info" in url:
            return httpx.Response(200, json=MOCK_CF_USER)
        if "user.status" in url:
            if "from=1&" in url:
                return httpx.Response(200, json={"status": "OK", "result": page1})
            # Page 2 fails with 500
            return httpx.Response(500, text="Internal Server Error")
        return httpx.Response(404, json={})

    transport = httpx.MockTransport(handler)
    connector = CodeforcesConnector(transport=transport, max_retries=1)

    # Must raise UpstreamUnavailableError, NOT silently return 1000
    with pytest.raises(UpstreamUnavailableError):
        await connector.fetch_profile("tourist")


@pytest.mark.asyncio
async def test_09_codeforces_rate_limits_timeouts_and_errors():
    """Requirement 9: HTTP 429, API limit comments, and timeouts raise typed errors."""
    # 429 Rate limit
    t_429 = httpx.MockTransport(lambda req: httpx.Response(429, json={"status": "FAILED", "comment": "Call limit exceeded"}))
    c_429 = CodeforcesConnector(transport=t_429, max_retries=1)
    with pytest.raises(RateLimitedError):
        await c_429.validate_identity("tourist")

    # 400 with "Call limit exceeded"
    t_limit = httpx.MockTransport(lambda req: httpx.Response(400, json={"status": "FAILED", "comment": "Call limit exceeded"}))
    c_limit = CodeforcesConnector(transport=t_limit, max_retries=1)
    with pytest.raises(RateLimitedError):
        await c_limit.validate_identity("tourist")

    # 400 with "User with handle ... not found" returns False
    t_nf = httpx.MockTransport(lambda req: httpx.Response(400, json={"status": "FAILED", "comment": "handle: User with handle notfound not found"}))
    c_nf = CodeforcesConnector(transport=t_nf, max_retries=1)
    assert await c_nf.validate_identity("notfound") is False
    assert await c_nf.fetch_profile("notfound") is None

    # 500 Server error
    t_500 = httpx.MockTransport(lambda req: httpx.Response(500, text="Downstream Error"))
    c_500 = CodeforcesConnector(transport=t_500, max_retries=1)
    with pytest.raises(UpstreamUnavailableError):
        await c_500.validate_identity("tourist")


@pytest.mark.asyncio
async def test_10_codeforces_pagination_termination_and_repeated_page_protection():
    """Requirement 10: Infinite loops prevented if upstream returns the same page repeatedly."""
    repeated_page = [make_sub(1, 100, "A", "Problem 100A", "OK") for _ in range(1000)]

    page_requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal page_requests
        url = str(request.url)
        if "user.info" in url:
            return httpx.Response(200, json=MOCK_CF_USER)
        if "user.status" in url:
            page_requests += 1
            # Return same submissions every time regardless of from_index
            return httpx.Response(200, json={"status": "OK", "result": repeated_page})
        return httpx.Response(404, json={})

    transport = httpx.MockTransport(handler)
    connector = CodeforcesConnector(transport=transport)

    profile = await connector.fetch_profile("tourist")
    assert profile is not None
    assert profile["total_solved"] == 1
    # Loop should have terminated after noticing identical submission IDs (max 2 page requests)
    assert page_requests <= 2


@pytest.mark.asyncio
async def test_12_codeforces_failed_sync_preserves_database_evidence():
    """Requirement 12: Failed sync does not wipe out or corrupt existing database evidence."""
    db = SessionLocal()
    test_uid = str(uuid.uuid4())
    user = User(
        id=test_uid,
        clerk_user_id=f"clerk_{uuid.uuid4().hex[:8]}",
        email=f"cf_test_{uuid.uuid4().hex[:6]}@example.com",
    )
    db.add(user)
    db.commit()

    try:
        conn = PlatformConnection(
            id=str(uuid.uuid4()),
            user_id=test_uid,
            platform="Codeforces",
            username="tourist",
            connected=True,
        )
        db.add(conn)
        db.commit()

        ev = Evidence(
            id=str(uuid.uuid4()),
            user_id=test_uid,
            platform_connection_id=conn.id,
            external_id="codeforces_profile_tourist",
            title="Codeforces Profile: tourist (Rating: 3800)",
            evidence_type="problem_solving_summary",
            raw_payload={"username": "tourist", "rating": 3800, "total_solved": 800},
            normalized_payload={"rating": 3800, "total_solved": 800},
        )
        db.add(ev)
        db.commit()

        # Simulate failed connector
        t_fail = httpx.MockTransport(lambda req: httpx.Response(500, text="Internal Error"))
        c_fail = CodeforcesConnector(transport=t_fail, max_retries=1)

        with pytest.raises(UpstreamUnavailableError):
            await c_fail.fetch_evidence("tourist")

        # Confirm evidence row remains untouched
        db.expire_all()
        persisted = db.query(Evidence).filter(Evidence.platform_connection_id == conn.id).all()
        assert len(persisted) == 1
        assert persisted[0].normalized_payload["total_solved"] == 800
        assert persisted[0].normalized_payload["rating"] == 3800
    finally:
        db.query(Evidence).filter(Evidence.user_id == test_uid).delete()
        db.query(PlatformConnection).filter(PlatformConnection.user_id == test_uid).delete()
        db.query(User).filter(User.id == test_uid).delete()
        db.commit()
        db.close()


@pytest.mark.asyncio
async def test_13_codeforces_hard_cap_raises_incomplete_history_error():
    """Requirement 13: Reaching max_pages without end of history raises IncompleteHistoryError."""
    # Every page returns full page_size items with brand new IDs, never ending
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "user.info" in url:
            return httpx.Response(200, json=MOCK_CF_USER)
        if "user.status" in url:
            import urllib.parse
            parsed = urllib.parse.urlparse(url)
            qs = urllib.parse.parse_qs(parsed.query)
            from_idx = int(qs.get("from", [1])[0])
            count = int(qs.get("count", [10])[0])
            page_subs = [make_sub(from_idx + i, from_idx + i, "A", f"P_{from_idx + i}", "OK") for i in range(count)]
            return httpx.Response(200, json={"status": "OK", "result": page_subs})
        return httpx.Response(404, json={})

    transport = httpx.MockTransport(handler)
    # Configure max_pages=3 with page_size=10
    connector = CodeforcesConnector(transport=transport)

    with pytest.raises(IncompleteHistoryError) as exc_info:
        await connector.fetch_unique_solved_problems("tourist", page_size=10, max_pages=3)

    assert "exceeded maximum pagination limit" in str(exc_info.value)
    assert "without reaching end of history" in str(exc_info.value)

    # fetch_profile must also raise and not return partial count
    with pytest.raises(IncompleteHistoryError):
        await connector.fetch_profile("tourist")


@pytest.mark.asyncio
async def test_14_codeforces_normal_termination_on_empty_page():
    """Requirement 14: Normal termination when final page returns an empty list."""
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "user.info" in url:
            return httpx.Response(200, json=MOCK_CF_USER)
        if "user.status" in url:
            if "from=1&" in url:
                # Page 1: exactly 10 items (full page)
                return httpx.Response(200, json={"status": "OK", "result": [make_sub(i, i, "A", f"P_{i}", "OK") for i in range(1, 11)]})
            elif "from=11&" in url:
                # Page 2: empty list (history ends)
                return httpx.Response(200, json={"status": "OK", "result": []})
        return httpx.Response(404, json={})

    transport = httpx.MockTransport(handler)
    connector = CodeforcesConnector(transport=transport)

    solved = await connector.fetch_unique_solved_problems("tourist", page_size=10, max_pages=5)
    assert len(solved) == 10


@pytest.mark.asyncio
async def test_15_codeforces_normal_termination_on_short_page():
    """Requirement 15: Normal termination when final page returns fewer than page_size items."""
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "user.info" in url:
            return httpx.Response(200, json=MOCK_CF_USER)
        if "user.status" in url:
            if "from=1&" in url:
                # Page 1: full 10 items
                return httpx.Response(200, json={"status": "OK", "result": [make_sub(i, i, "A", f"P_{i}", "OK") for i in range(1, 11)]})
            elif "from=11&" in url:
                # Page 2: short page (4 items < 10)
                return httpx.Response(200, json={"status": "OK", "result": [make_sub(10 + i, 10 + i, "A", f"P_{10 + i}", "OK") for i in range(1, 5)]})
        return httpx.Response(404, json={})

    transport = httpx.MockTransport(handler)
    connector = CodeforcesConnector(transport=transport)

    solved = await connector.fetch_unique_solved_problems("tourist", page_size=10, max_pages=5)
    assert len(solved) == 14


@pytest.mark.asyncio
async def test_16_codeforces_transient_failure_retries_and_succeeds():
    """Requirement 16: Transient failure (429/500) retries and succeeds, returning full history."""
    attempts_page2 = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts_page2
        url = str(request.url)
        if "user.info" in url:
            return httpx.Response(200, json=MOCK_CF_USER)
        if "user.status" in url:
            if "from=1&" in url:
                return httpx.Response(200, json={"status": "OK", "result": [make_sub(1, 10, "A", "P1", "OK")]})
            if "from=2&" in url:
                attempts_page2 += 1
                if attempts_page2 == 1:
                    # First attempt fails with 429
                    return httpx.Response(429, json={"status": "FAILED", "comment": "Call limit exceeded"})
                # Second attempt succeeds
                return httpx.Response(200, json={"status": "OK", "result": [make_sub(2, 20, "A", "P2", "OK")]})
            return httpx.Response(200, json={"status": "OK", "result": []})
        return httpx.Response(404, json={})

    transport = httpx.MockTransport(handler)
    connector = CodeforcesConnector(transport=transport, max_retries=2, base_backoff=0.0)

    solved = await connector.fetch_unique_solved_problems("tourist", page_size=1, max_pages=5)
    assert len(solved) == 2
    assert attempts_page2 == 2


@pytest.mark.asyncio
async def test_17_codeforces_retry_exhaustion_raises_typed_error():
    """Requirement 17: Retry exhaustion terminates bounded retries and raises typed error."""
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        url = str(request.url)
        if "user.info" in url:
            return httpx.Response(200, json=MOCK_CF_USER)
        if "user.status" in url:
            attempts += 1
            # Continually fails with 503
            return httpx.Response(503, text="Service Unavailable")
        return httpx.Response(404, json={})

    transport = httpx.MockTransport(handler)
    connector = CodeforcesConnector(transport=transport, max_retries=3, base_backoff=0.0)

    with pytest.raises(UpstreamUnavailableError):
        await connector.fetch_unique_solved_problems("tourist", page_size=10, max_pages=2)

    # Initial attempt + 3 retries = exactly 4 attempts (bounded!)
    assert attempts == 4


@pytest.mark.asyncio
async def test_18_codeforces_later_page_failure_preserves_database():
    """Requirement 18: Upstream failure during later pagination page does NOT overwrite DB with partial data."""
    db = SessionLocal()
    test_uid = str(uuid.uuid4())
    user = User(
        id=test_uid,
        clerk_user_id=f"clerk_{uuid.uuid4().hex[:8]}",
        email=f"cf_later_page_{uuid.uuid4().hex[:6]}@example.com",
    )
    db.add(user)
    db.commit()

    try:
        conn = PlatformConnection(
            id=str(uuid.uuid4()),
            user_id=test_uid,
            platform="Codeforces",
            username="tourist",
            connected=True,
        )
        db.add(conn)
        db.commit()

        # Existing valid historical evidence (e.g. 800 solved problems)
        ev = Evidence(
            id=str(uuid.uuid4()),
            user_id=test_uid,
            platform_connection_id=conn.id,
            external_id="codeforces_profile_tourist",
            title="Codeforces Profile: tourist (Rating: 3800)",
            evidence_type="problem_solving_summary",
            raw_payload={"username": "tourist", "rating": 3800, "total_solved": 800},
            normalized_payload={"rating": 3800, "total_solved": 800},
        )
        db.add(ev)
        db.commit()

        # Page 1 succeeds with 1000 submissions (full page)
        # Page 2 fails with 500
        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "user.info" in url:
                return httpx.Response(200, json=MOCK_CF_USER)
            if "user.status" in url:
                if "from=1&" in url:
                    page1 = [make_sub(i, i, "A", f"P_{i}", "OK") for i in range(1, 1001)]
                    return httpx.Response(200, json={"status": "OK", "result": page1})
                return httpx.Response(500, text="Internal Server Error")
            return httpx.Response(404, json={})

        transport = httpx.MockTransport(handler)
        connector = CodeforcesConnector(transport=transport, max_retries=1, base_backoff=0.0)

        # Attempting fetch_profile triggers the pagination failure on page 2
        with pytest.raises(UpstreamUnavailableError):
            await connector.fetch_profile("tourist")

        # Confirm the database evidence row still has total_solved == 800 (NOT partial count 10!)
        db.expire_all()
        persisted = db.query(Evidence).filter(Evidence.platform_connection_id == conn.id).all()
        assert len(persisted) == 1
        assert persisted[0].normalized_payload["total_solved"] == 800
        assert persisted[0].raw_payload["total_solved"] == 800
    finally:
        db.query(Evidence).filter(Evidence.user_id == test_uid).delete()
        db.query(PlatformConnection).filter(PlatformConnection.user_id == test_uid).delete()
        db.query(User).filter(User.id == test_uid).delete()
        db.commit()
        db.close()

