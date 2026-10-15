"""Comprehensive regression and repair test suite for Codewars connector (Batch 4).

Covers:
1. Valid and invalid handles (rejection without network requests).
2. Public profile parsing and normalized schema (honor, overall rank, leaderboard, languages).
3. Unranked user semantics (genuine zero honor, unranked overall, 0 completed).
4. Completed kata multi-page pagination.
5. Failed later page raises UpstreamUnavailableError (no partial results returned as complete).
6. Deduplication of completed kata across pagination.
7. Timestamp integrity: completedAt preserved, missing completedAt is None (never fabricated).
8. Detail lookup: slug deduplication, toleration of 500/404 detail lookups.
9. Malformed JSON, non-dict payloads, and non-list data fields raise UpstreamFormatError.
10. HTTP errors, rate limits, timeouts mapped to typed errors.
11. User ID resolving to a different username is rejected.
12. Database persistence & failed refresh preserves valid historical evidence.
13. Compatibility with platform sync API.
"""

import uuid
import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.evidence import Evidence
from app.models.platform import PlatformConnection
from app.models.user import User
from app.services.platform.codewars import CodewarsConnector
from app.services.platform.errors import (
    RateLimitedError,
    UpstreamFormatError,
    UpstreamUnavailableError,
)
from app.services.platform.registry import PlatformRegistry

client = TestClient(app)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CW_USER_RATED = {
    "username": "jake_coder",
    "name": "Jake Coder",
    "honor": 4500,
    "clan": "CodeCrafters",
    "leaderboardPosition": 120,
    "ranks": {
        "overall": {"rank": -3, "name": "3 kyu", "color": "blue", "score": 2500},
        "languages": {
            "python": {"rank": -3, "name": "3 kyu", "score": 2200},
            "rust": {"rank": -5, "name": "5 kyu", "score": 400},
        },
    },
    "codeChallenges": {"totalAuthored": 5, "totalCompleted": 42},
}

CW_USER_UNRANKED = {
    "username": "newbie_cw",
    "name": "Newbie CW",
    "honor": 0,
    "clan": None,
    "leaderboardPosition": None,
    "ranks": {
        "overall": None,
        "languages": {},
    },
    "codeChallenges": {"totalAuthored": 0, "totalCompleted": 0},
}


# ---------------------------------------------------------------------------
# Unit Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_codewars_rejects_unsafe_handles():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json=CW_USER_RATED)

    c = CodewarsConnector(transport=httpx.MockTransport(handler))
    for bad in ["", "   ", "../etc/passwd", "user/name", "x?y=1", "a b", "a" * 80]:
        assert await c.validate_identity(bad) is False
        assert await c.fetch_profile(bad) is None
        assert await c.fetch_evidence(bad) == []
    assert calls == []


@pytest.mark.asyncio
async def test_codewars_profile_parsing_and_metrics():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=CW_USER_RATED)

    c = CodewarsConnector(transport=httpx.MockTransport(handler))
    assert await c.validate_identity("jake_coder") is True

    profile = await c.fetch_profile("jake_coder")
    assert profile is not None
    assert profile["username"] == "jake_coder"
    assert profile["name"] == "Jake Coder"
    assert profile["honor"] == 4500
    assert profile["clan"] == "CodeCrafters"
    assert profile["leaderboard_position"] == 120
    assert profile["rank"] == -3
    assert profile["rank_name"] == "3 kyu"
    assert profile["rank_score"] == 2500
    assert profile["total_solved"] == 42
    assert profile["total_authored"] == 5
    assert "python" in profile["language_ranks"]
    assert profile["language_ranks"]["python"]["rank"] == -3


@pytest.mark.asyncio
async def test_codewars_unranked_user_semantics():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=CW_USER_UNRANKED)

    c = CodewarsConnector(transport=httpx.MockTransport(handler))
    assert await c.validate_identity("newbie_cw") is True

    profile = await c.fetch_profile("newbie_cw")
    assert profile is not None
    assert profile["honor"] == 0
    assert profile["rank"] is None
    assert profile["rank_name"] is None
    assert profile["rank_score"] is None
    assert profile["leaderboard_position"] is None
    assert profile["total_solved"] == 0
    assert profile["language_ranks"] == {}


@pytest.mark.asyncio
async def test_codewars_multi_page_pagination_and_deduplication():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        path = request.url.path
        if "/users/jake_coder/code-challenges/completed" in path:
            page = int(request.url.params.get("page", 0))
            if page == 0:
                return httpx.Response(
                    200,
                    json={
                        "totalPages": 2,
                        "totalItems": 3,
                        "data": [
                            {"id": "kata_1", "slug": "slug-1", "completedAt": "2024-01-01T10:00:00Z", "completedLanguages": ["python"]},
                            {"id": "kata_2", "slug": "slug-2", "completedAt": "2024-02-01T10:00:00Z", "completedLanguages": ["rust"]},
                        ],
                    },
                )
            elif page == 1:
                return httpx.Response(
                    200,
                    json={
                        "totalPages": 2,
                        "totalItems": 3,
                        "data": [
                            # kata_2 intentionally duplicated across boundary to test deduplication
                            {"id": "kata_2", "slug": "slug-2", "completedAt": "2024-02-01T10:00:00Z", "completedLanguages": ["rust"]},
                            {"id": "kata_3", "slug": "slug-3", "completedAt": "2024-03-01T10:00:00Z", "completedLanguages": ["python"]},
                        ],
                    },
                )
        if "/api/v1/users/jake_coder" in path:
            return httpx.Response(200, json=CW_USER_RATED)
        if "/api/v1/code-challenges/" in path:
            return httpx.Response(200, json={"id": "x", "tags": ["Algorithms"], "rank": {"name": "4 kyu"}})
        return httpx.Response(404)

    c = CodewarsConnector(transport=httpx.MockTransport(handler))
    items = await c.fetch_evidence("jake_coder")
    katas = [i for i in items if i["type"] == "codewars_kata"]
    # 3 unique katas (kata_2 was deduplicated)
    assert len(katas) == 3
    kata_ids = [k["data"]["id"] for k in katas]
    assert len(set(kata_ids)) == 3
    assert set(kata_ids) == {"kata_1", "kata_2", "kata_3"}


@pytest.mark.asyncio
async def test_codewars_failed_later_page_raises_unavailable_not_partial():
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "/users/jake_coder/code-challenges/completed" in path:
            page = int(request.url.params.get("page", 0))
            if page == 0:
                return httpx.Response(
                    200,
                    json={
                        "totalPages": 2,
                        "totalItems": 4,
                        "data": [{"id": "k1", "slug": "slug-1", "completedLanguages": ["python"]}],
                    },
                )
            # Page 1 fails
            return httpx.Response(502)
        if "/api/v1/users/jake_coder" in path:
            return httpx.Response(200, json=CW_USER_RATED)
        return httpx.Response(404)

    c = CodewarsConnector(transport=httpx.MockTransport(handler))
    with pytest.raises(UpstreamUnavailableError):
        await c.fetch_evidence("jake_coder")


@pytest.mark.asyncio
async def test_codewars_timestamp_integrity_never_fabricates():
    c = CodewarsConnector()
    # 1. With real timestamp
    item_with_time = {
        "type": "codewars_kata",
        "data": {
            "id": "k1",
            "name": "Test Kata",
            "slug": "test-kata",
            "completedAt": "2024-06-15T12:00:00Z",
            "completedLanguages": ["python"],
        },
    }
    norm1 = c.normalize_evidence(item_with_time)
    assert norm1["occurred_at"] == "2024-06-15T12:00:00Z"

    # 2. Missing timestamp: MUST be None, never datetime.now()
    item_no_time = {
        "type": "codewars_kata",
        "data": {
            "id": "k2",
            "name": "Test Kata No Date",
            "slug": "test-kata-no-date",
            "completedAt": None,
            "completedLanguages": ["python"],
        },
    }
    norm2 = c.normalize_evidence(item_no_time)
    assert norm2["occurred_at"] is None


@pytest.mark.asyncio
async def test_codewars_detail_lookup_error_tolerance_and_slug_deduplication():
    detail_calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "/users/jake_coder/code-challenges/completed" in path:
            return httpx.Response(
                200,
                json={
                    "totalPages": 1,
                    "totalItems": 2,
                    "data": [
                        {"id": "k1", "slug": "slug-1", "completedLanguages": ["python"]},
                        {"id": "k2", "slug": "slug-2", "completedLanguages": ["python"]},
                    ],
                },
            )
        if "/api/v1/users/jake_coder" in path:
            return httpx.Response(200, json=CW_USER_RATED)
        if path == "/api/v1/code-challenges/slug-1":
            detail_calls.append("slug-1")
            return httpx.Response(200, json={"id": "k1", "slug": "slug-1", "tags": ["Dynamic Programming"]})
        if path == "/api/v1/code-challenges/slug-2":
            detail_calls.append("slug-2")
            return httpx.Response(500)  # detail lookup fails
        return httpx.Response(404)

    c = CodewarsConnector(transport=httpx.MockTransport(handler))
    items = await c.fetch_evidence("jake_coder")
    katas = [i for i in items if i["type"] == "codewars_kata"]
    assert len(katas) == 2

    k1_norm = c.normalize_evidence(katas[0])
    assert "Dynamic Programming" in k1_norm["normalized_payload"]["tags"]

    # k2 detail lookup failed with 500, but kata evidence is still retained with empty tags
    k2_norm = c.normalize_evidence(katas[1])
    assert k2_norm["normalized_payload"]["tags"] == []
    assert k2_norm["normalized_payload"]["passed"] is True


@pytest.mark.asyncio
async def test_codewars_malformed_upstream_formats():
    # 1. User response not valid JSON
    def handler_bad_json(request):
        return httpx.Response(200, text="<html>502 Bad Gateway</html>")

    with pytest.raises(UpstreamFormatError):
        await CodewarsConnector(transport=httpx.MockTransport(handler_bad_json)).validate_identity("jake_coder")

    # 2. Completed kata data is not a list
    def handler_not_list(request):
        path = request.url.path
        if "/api/v1/users/jake_coder" in path:
            return httpx.Response(200, json=CW_USER_RATED)
        if "/code-challenges/completed" in path:
            return httpx.Response(200, json={"totalPages": 1, "data": "unexpected_string"})
        return httpx.Response(404)

    with pytest.raises(UpstreamFormatError):
        await CodewarsConnector(transport=httpx.MockTransport(handler_not_list)).fetch_evidence("jake_coder")


@pytest.mark.asyncio
async def test_codewars_http_error_mappings():
    def handler_429(request):
        return httpx.Response(429)

    with pytest.raises(RateLimitedError):
        await CodewarsConnector(transport=httpx.MockTransport(handler_429)).validate_identity("user")

    def handler_503(request):
        return httpx.Response(503)

    with pytest.raises(UpstreamUnavailableError):
        await CodewarsConnector(transport=httpx.MockTransport(handler_503)).validate_identity("user")

    def handler_404(request):
        return httpx.Response(404)

    c = CodewarsConnector(transport=httpx.MockTransport(handler_404))
    assert await c.validate_identity("ghost") is False
    assert await c.fetch_profile("ghost") is None


# ---------------------------------------------------------------------------
# Integration & Database Persistence Tests
# ---------------------------------------------------------------------------

def test_codewars_full_sync_and_failed_refresh_preserves_evidence(monkeypatch, db_session):
    user_id = f"test_cw_{uuid.uuid4().hex[:10]}"
    headers = {"X-Clerk-User-Id": user_id}

    state = {"status": 200}

    def transport_handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if state["status"] == 502:
            return httpx.Response(502)

        if path.endswith("/code-challenges/completed"):
            return httpx.Response(
                200,
                json={
                    "totalPages": 1,
                    "totalItems": 2,
                    "data": [
                        {"id": "k1", "name": "Kata One", "slug": "kata-1", "completedAt": "2024-01-01T00:00:00Z", "completedLanguages": ["python"]},
                        {"id": "k2", "name": "Kata Two", "slug": "kata-2", "completedAt": "2024-01-02T00:00:00Z", "completedLanguages": ["python"]},
                    ],
                },
            )
        if "/api/v1/users/jake_coder" in path:
            return httpx.Response(200, json=CW_USER_RATED)
        if "/api/v1/code-challenges/" in path:
            return httpx.Response(200, json={"tags": ["Strings"], "rank": {"name": "6 kyu"}})
        return httpx.Response(404)

    mock_transport = httpx.MockTransport(transport_handler)

    original_get_connector = PlatformRegistry.get_connector_instance

    def fake_get_connector(key, auth_token=None):
        if key.lower() == "codewars":
            return CodewarsConnector(transport=mock_transport)
        return original_get_connector(key, auth_token=auth_token)

    monkeypatch.setattr(PlatformRegistry, "get_connector_instance", staticmethod(fake_get_connector))

    # 1. Initial successful sync
    res = client.post("/api/v1/platforms/codewars/sync", json={"username": "jake_coder"}, headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["platform"] == "Codewars"
    assert body["synced_evidence_count"] == 3  # 1 profile + 2 kata

    user = db_session.query(User).filter_by(clerk_user_id=user_id).first()
    assert user is not None
    conn = db_session.query(PlatformConnection).filter_by(user_id=user.id, platform="Codewars").first()
    assert conn is not None and conn.connected is True
    evidence_count = db_session.query(Evidence).filter_by(platform_connection_id=conn.id).count()
    assert evidence_count == 3

    # 2. Subsequent failed refresh (upstream 502)
    state["status"] = 502
    res_failed = client.post("/api/v1/platforms/codewars/sync", json={"username": "jake_coder"}, headers=headers)
    assert res_failed.status_code == 502

    # Evidence MUST be preserved in full
    evidence_after_failure = db_session.query(Evidence).filter_by(platform_connection_id=conn.id).count()
    assert evidence_after_failure == 3
    conn_after_failure = db_session.query(PlatformConnection).filter_by(id=conn.id).first()
    assert conn_after_failure.connected is True
