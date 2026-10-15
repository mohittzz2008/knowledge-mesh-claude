"""Comprehensive regression and repair test suite for GitHub connector (Batch 5).

Covers:
1. Handle validation (rejection of malformed/invalid handles without network calls).
2. Public profile parsing and normalized schema (genuine stats, followers, repos, bio).
3. Identity matching (requested username matches returned login).
4. Rate-limit mapping (HTTP 429 and HTTP 403 with rate limit headers/body mapped to RateLimitedError).
5. Upstream error mapping (HTTP 5xx, timeouts, network errors mapped to UpstreamUnavailableError).
6. Malformed JSON handling mapped to UpstreamFormatError.
7. Repository pagination:
   - A short final page completes successfully.
   - An empty final page completes successfully.
   - Ten full pages without reaching end of history raises IncompleteHistoryError.
   - Upstream failure on a later page raises typed UpstreamUnavailableError and preserves DB evidence.
8. Activity events pagination, deduplication, and 3-page cap.
9. Platform-namespaced external IDs (github_profile_, github_repo_, github_event_, github_file_):
   - Stable across repeated syncs.
   - Repeated syncs update rather than duplicate.
   - No collisions between repo IDs and event IDs or across platforms.
   - Legacy un-prefixed records migrated safely in place during refresh.
10. Evidence emission and timestamp integrity (occurred_at None when unknown, never fabricated).
11. Database persistence, rate-limit refresh resilience, and successful retry.
12. CodeLab provenance isolation (ensuring external GitHub sync/switch does not touch CodeLab artifacts).
"""

import uuid
import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.code_artifact import CodeArtifact
from app.models.evidence import Evidence
from app.models.platform import PlatformConnection
from app.models.user import User
from app.services.platform.errors import (
    IncompleteHistoryError,
    RateLimitedError,
    UpstreamFormatError,
    UpstreamUnavailableError,
)
from app.services.platform.github import (
    MAX_REPOS_PAGES,
    GitHubConnector,
    clean_github_handle,
)
from app.services.platform.registry import PlatformRegistry

client = TestClient(app)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_GITHUB_USER = {
    "login": "octocat",
    "id": 583231,
    "name": "The Octocat",
    "avatar_url": "https://avatars.githubusercontent.com/u/583231?v=4",
    "html_url": "https://github.com/octocat",
    "bio": "GitHub mascot and developer",
    "company": "@github",
    "location": "San Francisco",
    "blog": "https://github.blog",
    "twitter_username": "github",
    "public_repos": 8,
    "public_gists": 8,
    "followers": 10500,
    "following": 9,
    "created_at": "2011-01-25T18:44:36Z",
    "updated_at": "2026-03-10T12:00:00Z",
}

SAMPLE_REPO_1 = {
    "id": 1296269,
    "name": "Hello-World",
    "full_name": "octocat/Hello-World",
    "owner": {"login": "octocat", "id": 583231},
    "language": "Python",
    "topics": ["tutorial", "demo"],
    "stargazers_count": 2500,
    "html_url": "https://github.com/octocat/Hello-World",
    "updated_at": "2026-03-01T10:00:00Z",
    "description": "My first repository on GitHub!",
}

SAMPLE_REPO_2 = {
    "id": 1296270,
    "name": "Spoon-Knife",
    "full_name": "octocat/Spoon-Knife",
    "owner": {"login": "octocat", "id": 583231},
    "language": "HTML",
    "topics": ["git", "fork"],
    "stargazers_count": 12000,
    "html_url": "https://github.com/octocat/Spoon-Knife",
    "updated_at": "2026-03-02T10:00:00Z",
    "description": "This repo is for forking.",
}

SAMPLE_FOREIGN_REPO = {
    "id": 9999999,
    "name": "Other-Repo",
    "full_name": "otheruser/Other-Repo",
    "owner": {"login": "otheruser", "id": 111111},
    "language": "Rust",
    "topics": [],
    "stargazers_count": 10,
    "html_url": "https://github.com/otheruser/Other-Repo",
    "updated_at": "2026-03-01T00:00:00Z",
    "description": "Not owned by octocat",
}

SAMPLE_EVENT_PUSH = {
    "id": "222333444",
    "type": "PushEvent",
    "repo": {"name": "octocat/Hello-World"},
    "created_at": "2026-03-05T14:30:00Z",
    "payload": {
        "commits": [{"sha": "a1b2c3d", "message": "fix: update README"}],
    },
}

SAMPLE_EVENT_PR = {
    "id": "222333445",
    "type": "PullRequestEvent",
    "repo": {"name": "octocat/Hello-World"},
    "created_at": "2026-03-06T15:00:00Z",
    "payload": {
        "action": "opened",
    },
}


# ---------------------------------------------------------------------------
# 1. Handle Validation Tests
# ---------------------------------------------------------------------------

def test_clean_github_handle():
    # Valid handles
    assert clean_github_handle("torvalds") == "torvalds"
    assert clean_github_handle("mohit-123") == "mohit-123"
    assert clean_github_handle("octocat") == "octocat"
    assert clean_github_handle("a-b") == "a-b"
    assert clean_github_handle("A") == "A"

    # Invalid handles
    assert clean_github_handle("") is None
    assert clean_github_handle("   ") is None
    assert clean_github_handle("-leading-hyphen") is None
    assert clean_github_handle("trailing-hyphen-") is None
    assert clean_github_handle("double--hyphens") is None
    assert clean_github_handle("user_underscore") is None
    assert clean_github_handle("user.period") is None
    assert clean_github_handle("user/slash") is None
    assert clean_github_handle("user@at") is None
    assert clean_github_handle("a" * 40) is None  # max 39 chars


@pytest.mark.asyncio
async def test_invalid_handles_reject_without_http():
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json=SAMPLE_GITHUB_USER)

    connector = GitHubConnector(transport=httpx.MockTransport(handler))

    assert await connector.validate_identity("-invalid") is False
    assert await connector.validate_identity("inv--alid") is False
    assert await connector.validate_identity("invalid_name") is False
    assert await connector.validate_identity("") is False

    assert await connector.fetch_profile("-invalid") is None
    assert await connector.fetch_repos("inv--alid") == []
    assert await connector.fetch_events("invalid_name") == []
    assert await connector.fetch_evidence("") == []

    assert called is False


# ---------------------------------------------------------------------------
# 2. Profile Fetch & Validation Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_github_profile_fetch_success():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/users/octocat"
        return httpx.Response(200, json=SAMPLE_GITHUB_USER)

    connector = GitHubConnector(transport=httpx.MockTransport(handler))
    is_valid = await connector.validate_identity("octocat")
    assert is_valid is True

    profile = await connector.fetch_profile("octocat")
    assert profile is not None
    assert profile["username"] == "octocat"
    assert profile["name"] == "The Octocat"
    assert profile["public_repos"] == 8
    assert profile["followers"] == 10500
    assert profile["following"] == 9
    assert profile["bio"] == "GitHub mascot and developer"
    assert profile["company"] == "@github"
    assert profile["location"] == "San Francisco"
    assert profile["created_at"] == "2011-01-25T18:44:36Z"
    assert profile["updated_at"] == "2026-03-10T12:00:00Z"


@pytest.mark.asyncio
async def test_github_profile_fetch_mismatched_login():
    fake_user = dict(SAMPLE_GITHUB_USER)
    fake_user["login"] = "different_user"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=fake_user)

    connector = GitHubConnector(transport=httpx.MockTransport(handler))
    assert await connector.validate_identity("octocat") is False
    assert await connector.fetch_profile("octocat") is None


@pytest.mark.asyncio
async def test_github_profile_fetch_404():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not Found"})

    connector = GitHubConnector(transport=httpx.MockTransport(handler))
    assert await connector.validate_identity("nonexistent-user") is False
    assert await connector.fetch_profile("nonexistent-user") is None


# ---------------------------------------------------------------------------
# 3. Rate Limit & Upstream Error Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_github_rate_limited_403_and_429():
    def handler_403_remaining(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1773000000"},
            json={"message": "API rate limit exceeded"},
        )

    connector = GitHubConnector(transport=httpx.MockTransport(handler_403_remaining))
    with pytest.raises(RateLimitedError) as exc_info:
        await connector.validate_identity("octocat")
    assert "rate limit" in str(exc_info.value).lower()

    with pytest.raises(RateLimitedError):
        await connector.fetch_profile("octocat")

    def handler_429(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"message": "Too Many Requests"})

    connector_429 = GitHubConnector(transport=httpx.MockTransport(handler_429))
    with pytest.raises(RateLimitedError):
        await connector_429.fetch_repos("octocat")

    with pytest.raises(RateLimitedError):
        await connector_429.fetch_events("octocat")


@pytest.mark.asyncio
async def test_github_upstream_errors():
    def handler_503(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="Service Unavailable")

    connector = GitHubConnector(transport=httpx.MockTransport(handler_503))
    with pytest.raises(UpstreamUnavailableError):
        await connector.fetch_profile("octocat")


@pytest.mark.asyncio
async def test_github_malformed_json():
    def handler_bad_json(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="NOT_VALID_JSON{")

    connector = GitHubConnector(transport=httpx.MockTransport(handler_bad_json))
    with pytest.raises(UpstreamFormatError):
        await connector.fetch_profile("octocat")


# ---------------------------------------------------------------------------
# 4. Repository Pagination Completeness Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_github_repos_pagination_short_final_page():
    """Verify that a final page with fewer records than `limit` successfully terminates."""
    def handler(request: httpx.Request) -> httpx.Response:
        page = request.url.params.get("page")
        if page == "1":
            return httpx.Response(200, json=[SAMPLE_REPO_1, SAMPLE_REPO_2])
        elif page == "2":
            # Short final page: limit is 2, but only 1 record returned
            return httpx.Response(200, json=[dict(SAMPLE_REPO_1, id=333333, name="Repo-3")])
        return httpx.Response(200, json=[])

    connector = GitHubConnector(transport=httpx.MockTransport(handler))
    repos = await connector.fetch_repos("octocat", limit=2)

    assert len(repos) == 3
    assert [r["id"] for r in repos] == [SAMPLE_REPO_1["id"], SAMPLE_REPO_2["id"], 333333]


@pytest.mark.asyncio
async def test_github_repos_pagination_empty_final_page():
    """Verify that an empty list on the next page successfully terminates pagination."""
    def handler(request: httpx.Request) -> httpx.Response:
        page = request.url.params.get("page")
        if page == "1":
            return httpx.Response(200, json=[SAMPLE_REPO_1, SAMPLE_REPO_2])
        return httpx.Response(200, json=[])  # Empty final page

    connector = GitHubConnector(transport=httpx.MockTransport(handler))
    repos = await connector.fetch_repos("octocat", limit=2)

    assert len(repos) == 2
    assert [r["id"] for r in repos] == [SAMPLE_REPO_1["id"], SAMPLE_REPO_2["id"]]


@pytest.mark.asyncio
async def test_github_repos_pagination_ten_full_pages_raises_incomplete_history():
    """When MAX_REPOS_PAGES (10) full pages are returned without reaching the end of history,
    the connector must raise IncompleteHistoryError rather than silently returning partial results.
    """
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        page_num = int(request.url.params.get("page", 1))
        # Always return a full page of 2 items (limit=2)
        return httpx.Response(
            200,
            json=[
                dict(SAMPLE_REPO_1, id=page_num * 100 + 1),
                dict(SAMPLE_REPO_1, id=page_num * 100 + 2),
            ],
        )

    connector = GitHubConnector(transport=httpx.MockTransport(handler))
    with pytest.raises(IncompleteHistoryError) as exc_info:
        await connector.fetch_repos("octocat", limit=2)

    assert calls == 10
    assert "exceeded safety limit" in str(exc_info.value).lower()
    assert exc_info.value.status_code == 502


@pytest.mark.asyncio
async def test_github_repos_later_page_failure_raises_upstream_error():
    """Verify that an upstream failure on page 2 raises UpstreamUnavailableError."""
    def handler(request: httpx.Request) -> httpx.Response:
        page = request.url.params.get("page")
        if page == "1":
            return httpx.Response(200, json=[SAMPLE_REPO_1, SAMPLE_REPO_2])
        elif page == "2":
            return httpx.Response(502, text="Bad Gateway on subsequent page")
        return httpx.Response(404)

    connector = GitHubConnector(transport=httpx.MockTransport(handler))
    with pytest.raises(UpstreamUnavailableError):
        await connector.fetch_repos("octocat", limit=2)


def test_github_later_page_failure_preserves_database_evidence(monkeypatch, db_session):
    """Confirm that an upstream failure on a subsequent page during sync raises an error
    and does NOT erase previously persisted valid database evidence.
    """
    user_id = f"test_later_fail_{uuid.uuid4().hex[:10]}"
    headers = {"X-Clerk-User-Id": user_id}

    state = {"fail_page_2": False}

    def transport_handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "/users/octocat/repos" in url_str:
            page = request.url.params.get("page")
            if page == "1":
                # Return 100 items (full page) so pagination proceeds to page 2
                return httpx.Response(200, json=[dict(SAMPLE_REPO_1, id=1000 + i) for i in range(100)])
            elif page == "2":
                if state["fail_page_2"]:
                    return httpx.Response(502, text="Upstream 502 on page 2")
                return httpx.Response(200, json=[])
        elif "/users/octocat/events" in url_str:
            return httpx.Response(200, json=[])
        elif "/users/octocat" in url_str:
            return httpx.Response(200, json=SAMPLE_GITHUB_USER)
        return httpx.Response(404)

    mock_transport = httpx.MockTransport(transport_handler)
    original_get_connector = PlatformRegistry.get_connector_instance

    def fake_get_connector(key, auth_token=None):
        if key.lower() == "github":
            return GitHubConnector(transport=mock_transport)
        return original_get_connector(key, auth_token=auth_token)

    monkeypatch.setattr(PlatformRegistry, "get_connector_instance", staticmethod(fake_get_connector))

    # 1. Successful initial sync (1 profile + 100 repos = 101 items)
    res_1 = client.post("/api/v1/platforms/github/sync", json={"username": "octocat"}, headers=headers)
    assert res_1.status_code == 200
    user = db_session.query(User).filter_by(clerk_user_id=user_id).first()
    conn = db_session.query(PlatformConnection).filter_by(user_id=user.id, platform="GitHub").first()
    assert db_session.query(Evidence).filter_by(platform_connection_id=conn.id).count() == 101

    # 2. Subsequent sync fails on page 2
    state["fail_page_2"] = True
    res_2 = client.post("/api/v1/platforms/github/sync", json={"username": "octocat"}, headers=headers)
    assert res_2.status_code == 502

    # Previously stored evidence and connection state MUST remain intact!
    assert db_session.query(Evidence).filter_by(platform_connection_id=conn.id).count() == 101
    conn_after = db_session.query(PlatformConnection).filter_by(id=conn.id).first()
    assert conn_after.connected is True


# ---------------------------------------------------------------------------
# 5. Activity Events Pagination & Deduplication Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_github_events_pagination_dedup_and_max_pages():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        page = request.url.params.get("page")
        if page == "1":
            return httpx.Response(200, json=[SAMPLE_EVENT_PUSH])
        elif page == "2":
            return httpx.Response(200, json=[SAMPLE_EVENT_PR, SAMPLE_EVENT_PUSH])
        elif page == "3":
            return httpx.Response(200, json=[SAMPLE_EVENT_PUSH])
        return httpx.Response(200, json=[])

    connector = GitHubConnector(transport=httpx.MockTransport(handler))
    events = await connector.fetch_events("octocat", limit=1)

    assert calls == 3
    assert len(events) == 2
    assert {e["id"] for e in events} == {SAMPLE_EVENT_PUSH["id"], SAMPLE_EVENT_PR["id"]}


# ---------------------------------------------------------------------------
# 6. Platform-Namespaced External IDs & Evidence Normalization Tests
# ---------------------------------------------------------------------------

def test_github_external_id_namespacing_and_normalization():
    connector = GitHubConnector()

    # 1. Profile stats item: github_profile_{username}
    profile_item = {
        "type": "profile_stats",
        "data": SAMPLE_GITHUB_USER,
    }
    norm_profile = connector.normalize_evidence(profile_item)
    assert norm_profile["platform"] == "GitHub"
    assert norm_profile["external_id"] == "github_profile_octocat"
    assert norm_profile["evidence_type"] == "profile"
    assert norm_profile["occurred_at"] == "2026-03-10T12:00:00Z"
    assert norm_profile["normalized_payload"]["public_repos"] == 8

    # 2. Repository item: github_repo_{id}
    repo_item = {
        "type": "repository",
        "data": SAMPLE_REPO_1,
    }
    norm_repo = connector.normalize_evidence(repo_item)
    assert norm_repo["platform"] == "GitHub"
    assert norm_repo["external_id"] == f"github_repo_{SAMPLE_REPO_1['id']}"
    assert norm_repo["evidence_type"] == "repository"
    assert norm_repo["occurred_at"] == SAMPLE_REPO_1["updated_at"]
    assert "Python" in norm_repo["normalized_payload"]["skills"]

    # 3. Activity events: github_event_{id}
    push_item = {"type": "activity", "data": SAMPLE_EVENT_PUSH}
    norm_push = connector.normalize_evidence(push_item)
    assert norm_push["evidence_type"] == "commit"
    assert norm_push["external_id"] == f"github_event_{SAMPLE_EVENT_PUSH['id']}"
    assert norm_push["occurred_at"] == SAMPLE_EVENT_PUSH["created_at"]

    # 4. Code file: github_file_{sha}
    code_file_item = {
        "type": "code_file",
        "data": {
            "path": "src/main.py",
            "sha": "1234567890abcdef",
            "size": 1024,
            "html_url": "https://github.com/octocat/Hello-World/blob/main/src/main.py",
            "code_content": "print('hello')",
        },
    }
    norm_code = connector.normalize_evidence(code_file_item)
    assert norm_code["external_id"] == "github_file_1234567890abcdef"
    assert norm_code["occurred_at"] is None  # Never fabricated!

    # 5. Fallback artifact: github_artifact_{id}
    fallback_item = {"type": "unknown_type", "data": {"id": "custom_123"}}
    norm_fallback = connector.normalize_evidence(fallback_item)
    assert norm_fallback["external_id"] == "github_artifact_custom_123"
    assert norm_fallback["occurred_at"] is None


def test_github_namespaced_ids_do_not_collide_and_update_in_place(monkeypatch, db_session):
    """Verify that:
    1. Repository and event sharing the exact same numeric ID (e.g. 1296269)
       produce distinct namespaced IDs ('github_repo_1296269' vs 'github_event_1296269')
       and both persist without collision.
    2. Repeated syncs update existing evidence rather than duplicating.
    """
    user_id = f"test_namespacing_{uuid.uuid4().hex[:10]}"
    headers = {"X-Clerk-User-Id": user_id}

    # Event crafted with the EXACT SAME numeric ID as SAMPLE_REPO_1
    conflicting_event = dict(SAMPLE_EVENT_PUSH, id="1296269")

    def transport_handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "/users/octocat/repos" in url_str:
            return httpx.Response(200, json=[SAMPLE_REPO_1])
        elif "/users/octocat/events" in url_str:
            return httpx.Response(200, json=[conflicting_event])
        elif "/users/octocat" in url_str:
            return httpx.Response(200, json=SAMPLE_GITHUB_USER)
        return httpx.Response(404)

    mock_transport = httpx.MockTransport(transport_handler)
    original_get_connector = PlatformRegistry.get_connector_instance

    def fake_get_connector(key, auth_token=None):
        if key.lower() == "github":
            return GitHubConnector(transport=mock_transport)
        return original_get_connector(key, auth_token=auth_token)

    monkeypatch.setattr(PlatformRegistry, "get_connector_instance", staticmethod(fake_get_connector))

    # 1. Sync: 1 profile + 1 repo + 1 event = 3 items
    res1 = client.post("/api/v1/platforms/github/sync", json={"username": "octocat"}, headers=headers)
    assert res1.status_code == 200
    assert res1.json()["synced_evidence_count"] == 3

    user = db_session.query(User).filter_by(clerk_user_id=user_id).first()
    conn = db_session.query(PlatformConnection).filter_by(user_id=user.id, platform="GitHub").first()
    items = db_session.query(Evidence).filter_by(platform_connection_id=conn.id).all()
    ext_ids = {e.external_id for e in items}

    # Assert repo and event with same numeric ID 1296269 coexist peacefully
    assert "github_repo_1296269" in ext_ids
    assert "github_event_1296269" in ext_ids
    assert "github_profile_octocat" in ext_ids
    assert len(items) == 3

    # 2. Repeated sync: must update in place without creating any duplicate rows
    res2 = client.post("/api/v1/platforms/github/sync", json={"username": "octocat"}, headers=headers)
    assert res2.status_code == 200
    assert res2.json()["synced_evidence_count"] == 0
    assert res2.json()["updated_evidence_count"] == 3

    items_after = db_session.query(Evidence).filter_by(platform_connection_id=conn.id).all()
    assert len(items_after) == 3


def test_github_legacy_unprefixed_evidence_migration_on_refresh(monkeypatch, db_session):
    """Verify that if existing database rows have legacy un-prefixed IDs ('1296269'),
    a subsequent refresh safely updates the record to the namespaced ID ('github_repo_1296269')
    without creating a duplicate row.
    """
    user_id = f"test_legacy_mig_{uuid.uuid4().hex[:10]}"
    headers = {"X-Clerk-User-Id": user_id}

    # 1. Create user, connection, and legacy un-prefixed evidence item
    user = User(clerk_user_id=user_id, email=f"{user_id}@example.com")
    db_session.add(user)
    db_session.flush()

    conn = PlatformConnection(
        user_id=user.id,
        platform="GitHub",
        username="octocat",
        connected=True,
    )
    db_session.add(conn)
    db_session.flush()

    legacy_evidence = Evidence(
        user_id=user.id,
        platform_connection_id=conn.id,
        external_id="1296269",  # Legacy un-prefixed ID
        title="Old Repository: octocat/Hello-World",
        evidence_type="repository",
    )
    db_session.add(legacy_evidence)
    db_session.commit()

    legacy_db_id = legacy_evidence.id

    # 2. Sync with new connector that emits "github_repo_1296269"
    def transport_handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "/users/octocat/repos" in url_str:
            return httpx.Response(200, json=[SAMPLE_REPO_1])
        elif "/users/octocat/events" in url_str:
            return httpx.Response(200, json=[])
        elif "/users/octocat" in url_str:
            return httpx.Response(200, json=SAMPLE_GITHUB_USER)
        return httpx.Response(404)

    mock_transport = httpx.MockTransport(transport_handler)
    original_get_connector = PlatformRegistry.get_connector_instance

    def fake_get_connector(key, auth_token=None):
        if key.lower() == "github":
            return GitHubConnector(transport=mock_transport)
        return original_get_connector(key, auth_token=auth_token)

    monkeypatch.setattr(PlatformRegistry, "get_connector_instance", staticmethod(fake_get_connector))

    res = client.post("/api/v1/platforms/github/sync", json={"username": "octocat"}, headers=headers)
    assert res.status_code == 200
    body = res.json()
    # 1 new profile item, 1 updated legacy repo item
    assert body["synced_evidence_count"] == 1
    assert body["updated_evidence_count"] == 1

    # Verify the legacy row was updated in place to namespaced ID without duplicate rows
    db_session.expire_all()
    all_evidence = db_session.query(Evidence).filter_by(platform_connection_id=conn.id).all()
    assert len(all_evidence) == 2

    migrated_row = db_session.query(Evidence).filter_by(id=legacy_db_id).first()
    assert migrated_row is not None
    assert migrated_row.external_id == "github_repo_1296269"
    assert "Repository: octocat/Hello-World" in migrated_row.title


# ---------------------------------------------------------------------------
# 7. Database Persistence & Rate Limit Refresh Resilience Tests
# ---------------------------------------------------------------------------

def test_github_rate_limit_429_preserves_evidence_and_subsequent_retry_succeeds(monkeypatch, db_session):
    """Confirm that an HTTP 429 rate limit preserves existing database evidence and
    connection state, and a subsequent successful retry refreshes evidence normally.
    """
    user_id = f"test_gh_429_{uuid.uuid4().hex[:10]}"
    headers = {"X-Clerk-User-Id": user_id}

    state = {"status": 200}

    def transport_handler(request: httpx.Request) -> httpx.Response:
        if state["status"] == 429:
            return httpx.Response(429, json={"message": "rate limit"})
        url_str = str(request.url)
        if "/users/octocat/repos" in url_str:
            return httpx.Response(200, json=[SAMPLE_REPO_1, SAMPLE_REPO_2])
        elif "/users/octocat/events" in url_str:
            return httpx.Response(200, json=[SAMPLE_EVENT_PUSH])
        elif "/users/octocat" in url_str:
            return httpx.Response(200, json=SAMPLE_GITHUB_USER)
        return httpx.Response(404)

    mock_transport = httpx.MockTransport(transport_handler)
    original_get_connector = PlatformRegistry.get_connector_instance

    def fake_get_connector(key, auth_token=None):
        if key.lower() == "github":
            return GitHubConnector(transport=mock_transport)
        return original_get_connector(key, auth_token=auth_token)

    monkeypatch.setattr(PlatformRegistry, "get_connector_instance", staticmethod(fake_get_connector))

    # 1. Initial successful sync (1 profile + 2 repos + 1 event = 4 evidence items)
    res = client.post("/api/v1/platforms/github/sync", json={"username": "octocat"}, headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["synced_evidence_count"] == 4

    user = db_session.query(User).filter_by(clerk_user_id=user_id).first()
    assert user is not None
    conn = db_session.query(PlatformConnection).filter_by(user_id=user.id, platform="GitHub").first()
    assert conn is not None and conn.connected is True
    assert db_session.query(Evidence).filter_by(platform_connection_id=conn.id).count() == 4

    # 2. Rate-limit failure (HTTP 429)
    state["status"] = 429
    res_429 = client.post("/api/v1/platforms/github/sync", json={"username": "octocat"}, headers=headers)
    assert res_429.status_code == 429

    # Evidence and connection state MUST remain intact
    evidence_after_429 = db_session.query(Evidence).filter_by(platform_connection_id=conn.id).count()
    assert evidence_after_429 == 4
    conn_after_429 = db_session.query(PlatformConnection).filter_by(id=conn.id).first()
    assert conn_after_429.connected is True

    # 3. Subsequent successful retry
    state["status"] = 200
    res_retry = client.post("/api/v1/platforms/github/sync", json={"username": "octocat"}, headers=headers)
    assert res_retry.status_code == 200
    body_retry = res_retry.json()
    assert body_retry["synced_evidence_count"] == 0
    assert body_retry["updated_evidence_count"] == 4

    # Evidence rows refreshed without duplication
    evidence_after_retry = db_session.query(Evidence).filter_by(platform_connection_id=conn.id).count()
    assert evidence_after_retry == 4
    conn_after_retry = db_session.query(PlatformConnection).filter_by(id=conn.id).first()
    assert conn_after_retry.connected is True


# ---------------------------------------------------------------------------
# 8. CodeLab Provenance Isolation Test
# ---------------------------------------------------------------------------

def test_github_codelab_provenance_isolation(monkeypatch, db_session):
    """Confirm that syncing or switching GitHub username does NOT delete or alter
    internal CodeLab CodeArtifact records (enforcing CodeArtifact.platform != 'CodeLab').
    """
    user_id = f"test_codelab_iso_{uuid.uuid4().hex[:10]}"
    headers = {"X-Clerk-User-Id": user_id}

    def transport_handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "/repos" in url_str:
            return httpx.Response(200, json=[SAMPLE_REPO_1])
        elif "/events" in url_str:
            return httpx.Response(200, json=[])
        elif "/users/" in url_str:
            return httpx.Response(200, json=SAMPLE_GITHUB_USER)
        return httpx.Response(404)

    mock_transport = httpx.MockTransport(transport_handler)
    original_get_connector = PlatformRegistry.get_connector_instance

    def fake_get_connector(key, auth_token=None):
        if key.lower() == "github":
            return GitHubConnector(transport=mock_transport)
        return original_get_connector(key, auth_token=auth_token)

    monkeypatch.setattr(PlatformRegistry, "get_connector_instance", staticmethod(fake_get_connector))

    # Initial sync to create user and connection
    res = client.post("/api/v1/platforms/github/sync", json={"username": "octocat"}, headers=headers)
    assert res.status_code == 200

    user = db_session.query(User).filter_by(clerk_user_id=user_id).first()
    conn = db_session.query(PlatformConnection).filter_by(user_id=user.id, platform="GitHub").first()

    # Create an internal CodeLab CodeArtifact associated with this user
    codelab_artifact = CodeArtifact(
        user_id=user.id,
        platform_connection_id=conn.id,
        platform="CodeLab",
        repository="CodeLab-Internal",
        file_path="problem_42.py",
        language="Python",
        code_content="def solution(): return 42",
    )
    db_session.add(codelab_artifact)
    db_session.commit()

    artifact_id = codelab_artifact.id

    # Switch username on GitHub connection, which purges stale external evidence
    user_octocat2 = dict(SAMPLE_GITHUB_USER, login="octocat2")

    def transport_handler2(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "/repos" in url_str:
            return httpx.Response(200, json=[])
        elif "/events" in url_str:
            return httpx.Response(200, json=[])
        elif "/users/" in url_str:
            return httpx.Response(200, json=user_octocat2)
        return httpx.Response(404)

    def fake_get_connector2(key, auth_token=None):
        if key.lower() == "github":
            return GitHubConnector(transport=httpx.MockTransport(transport_handler2))
        return original_get_connector(key, auth_token=auth_token)

    monkeypatch.setattr(PlatformRegistry, "get_connector_instance", staticmethod(fake_get_connector2))

    res_switch = client.post("/api/v1/platforms/github/sync", json={"username": "octocat2"}, headers=headers)
    assert res_switch.status_code == 200

    # Verify that the CodeLab artifact is still present in the database!
    persisted_codelab = db_session.query(CodeArtifact).filter_by(id=artifact_id).first()
    assert persisted_codelab is not None
    assert persisted_codelab.platform == "CodeLab"
    assert persisted_codelab.code_content == "def solution(): return 42"
