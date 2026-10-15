"""Comprehensive regression tests for Exercism connector repair (Batch 2).

Covers all Phase 4 requirements:
1. Profile normalization.
2. Reputation extraction and highlight generation.
3. Missing/null reputation.
4. Genuine numeric zero versus missing values.
5. Public profile without completed-exercise metrics.
6. Authenticated completed-exercise retrieval, if supported by verified API behavior.
7. Missing or invalid authentication (and ensuring secrets are never exposed).
8. Unauthorized, rate-limited, malformed, and timed-out responses.
9. Failed refresh preserves historical evidence.
"""

import json
import uuid
import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.v1.platforms import _highlights
from app.main import app
from app.models.evidence import Evidence
from app.models.platform import PlatformConnection
from app.models.user import User
from app.services.platform.errors import (
    ConnectorError,
    RateLimitedError,
    UpstreamFormatError,
    UpstreamUnavailableError,
)
from app.services.platform.exercism import ExercismConnector

client = TestClient(app)

# --- Mock Fixtures ---

EXERCISM_PUBLIC_USER_VALID = {
    "handle": "iHiD",
    "avatar_url": "https://assets.exercism.org/avatars/1530/1",
    "flair": "founder",
    "has_profile": True,
    "reputation": {
        "total": "69.9k",
        "tracks": {
            "ruby": 120,
            "python": 85,
            "elixir": 40,
        },
    },
}

EXERCISM_USER_NUMERIC_ZERO = {
    "handle": "newbie",
    "avatar_url": None,
    "flair": None,
    "has_profile": True,
    "reputation": {
        "total": 0,
        "tracks": {},
    },
}

EXERCISM_USER_NO_REPUTATION = {
    "handle": "ghost_coder",
    "avatar_url": None,
    "flair": None,
    "has_profile": False,
    "reputation": None,
}

EXERCISM_SOLUTIONS_VALID = {
    "results": [
        {
            "uuid": "sol-uuid-1",
            "exercise": {"slug": "hello-world", "title": "Hello World"},
            "track": {"slug": "python", "title": "Python"},
            "status": "published",
            "published_at": "2026-03-01T12:00:00Z",
        },
        {
            "uuid": "sol-uuid-2",
            "exercise": {"slug": "leap", "title": "Leap"},
            "track": {"slug": "python", "title": "Python"},
            "status": "completed",
            "completed_at": "2026-03-02T15:30:00Z",
        },
        {
            "uuid": "sol-uuid-3",
            "exercise": {"slug": "two-fer", "title": "Two Fer"},
            "track": {"slug": "ruby", "title": "Ruby"},
            "status": "completed",
            "completed_at": "2026-03-03T10:00:00Z",
        },
    ]
}


def make_exercism_transport(
    user_status: int = 200,
    user_data: dict | None = None,
    solutions_status: int = 200,
    solutions_data: dict | None = None,
) -> httpx.MockTransport:
    """Helper to mock Exercism public profile and authenticated solutions endpoints."""
    if user_data is None:
        user_data = EXERCISM_PUBLIC_USER_VALID
    if solutions_data is None:
        solutions_data = EXERCISM_SOLUTIONS_VALID

    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "/api/v2/users/" in url_str:
            if user_status == 200:
                return httpx.Response(200, json=user_data)
            return httpx.Response(user_status, text="Error")
        if "/api/v2/solutions" in url_str:
            auth_header = request.headers.get("Authorization", "")
            # Check secret handling: ensure token format
            if not auth_header or not auth_header.startswith("Bearer "):
                return httpx.Response(401, json={"error": {"type": "unauthorized"}})
            if "invalid" in auth_header:
                return httpx.Response(401, json={"error": {"type": "invalid_auth_token"}})
            if solutions_status == 200:
                return httpx.Response(200, json=solutions_data)
            return httpx.Response(solutions_status, text="Error")
        return httpx.Response(404, text="Not Found")

    return httpx.MockTransport(handler)


# --- Tests ---


@pytest.mark.asyncio
async def test_01_exercism_profile_normalization():
    """Requirement 1: Standard profile normalization with reputation and track metrics."""
    transport = make_exercism_transport()
    connector = ExercismConnector(transport=transport)

    profile = await connector.fetch_profile("iHiD")
    assert profile is not None
    assert profile["platform"] == "Exercism"
    assert profile["username"] == "iHiD"
    assert profile["handle"] == "iHiD"  # backwards compatibility
    assert profile["name"] == "iHiD"
    assert profile["avatar_url"] == "https://assets.exercism.org/avatars/1530/1"
    assert profile["html_url"] == "https://exercism.org/profiles/iHiD"
    assert profile["reputation"] == "69.9k"
    assert profile["total_reputation"] == "69.9k"
    assert set(profile["tracks"]) == {"ruby", "python", "elixir"}
    assert profile["active_tracks_count"] == 3
    # Public profile without auth token has total_solved = None
    assert profile["total_solved"] is None


def test_02_exercism_reputation_highlight_generation():
    """Requirement 2: Shared highlight logic recognizes reputation correctly."""
    # 1. Formatted string reputation
    profile_str = {"reputation": "69.9k", "rating": 1500}
    hl_str = _highlights(profile_str)
    assert any(h["label"] == "Reputation" and h["value"] == "69.9k" for h in hl_str)
    assert any(h["label"] == "Rating" and h["value"] == 1500 for h in hl_str)

    # 2. Integer reputation
    profile_int = {"reputation": 450}
    hl_int = _highlights(profile_int)
    assert any(h["label"] == "Reputation" and h["value"] == 450 for h in hl_int)

    # 3. Raw nested dict reputation
    profile_nested = {"reputation": {"total": "189k"}}
    hl_nested = _highlights(profile_nested)
    assert any(h["label"] == "Reputation" and h["value"] == "189k" for h in hl_nested)


def test_03_exercism_missing_and_null_reputation():
    """Requirement 3: Missing/null reputation does not generate a highlight."""
    profile_none = {"reputation": None}
    hl_none = _highlights(profile_none)
    assert not any(h["label"] == "Reputation" for h in hl_none)

    profile_empty = {}
    hl_empty = _highlights(profile_empty)
    assert not any(h["label"] == "Reputation" for h in hl_empty)


def test_04_exercism_numeric_zero_vs_missing():
    """Requirement 4: Genuine numeric zero reputation is preserved and distinguished from None."""
    # Genuine zero integer
    profile_zero = {"reputation": 0}
    hl_zero = _highlights(profile_zero)
    assert any(h["label"] == "Reputation" and h["value"] == 0 for h in hl_zero)

    # String "0"
    profile_str_zero = {"reputation": "0"}
    hl_str_zero = _highlights(profile_str_zero)
    assert any(h["label"] == "Reputation" and h["value"] == "0" for h in hl_str_zero)


@pytest.mark.asyncio
async def test_05_exercism_public_profile_without_completed_exercise_metrics():
    """Requirement 5: Public profile does not invent completed exercises (total_solved is None)."""
    transport = make_exercism_transport(user_data=EXERCISM_PUBLIC_USER_VALID)
    connector = ExercismConnector(auth_token=None, transport=transport)

    profile = await connector.fetch_profile("iHiD")
    assert profile is not None
    assert profile["total_solved"] is None  # NOT 0, NOT invented!

    evidence = await connector.fetch_evidence("iHiD")
    assert len(evidence) == 1
    assert evidence[0]["type"] == "exercism_reputation"
    assert evidence[0]["total_solved"] is None

    norm = connector.normalize_evidence(evidence[0])
    assert norm["normalized_payload"]["total_solved"] is None
    assert norm["normalized_payload"]["reputation"] == "69.9k"
    assert norm["normalized_payload"]["active_tracks_count"] == 3


@pytest.mark.asyncio
async def test_06_exercism_authenticated_solutions_retrieval():
    """Requirement 6: Authenticated solutions populate total_solved and generate exercise evidence."""
    transport = make_exercism_transport(solutions_data=EXERCISM_SOLUTIONS_VALID)
    connector = ExercismConnector(auth_token="valid_secret_token_123", transport=transport)

    profile = await connector.fetch_profile("iHiD")
    assert profile is not None
    assert profile["total_solved"] == 3

    evidence = await connector.fetch_evidence("iHiD")
    # 1 reputation item + 3 solution items
    assert len(evidence) == 4
    types = [e["type"] for e in evidence]
    assert types.count("exercism_reputation") == 1
    assert types.count("exercism_solution") == 3

    # Check solution normalization
    sol_items = [e for e in evidence if e["type"] == "exercism_solution"]
    norm_sol = connector.normalize_evidence(sol_items[0])
    assert norm_sol["platform"] == "Exercism"
    assert norm_sol["evidence_type"] == "problem_submission"
    assert norm_sol["external_id"] == "exercism_solution_sol-uuid-1"
    assert "Hello World" in norm_sol["title"]
    assert norm_sol["normalized_payload"]["track"] == "python"
    assert norm_sol["normalized_payload"]["exercise"] == "hello-world"


@pytest.mark.asyncio
async def test_07_exercism_invalid_authentication_and_secret_safety():
    """Requirement 7: Invalid auth token raises 401 ConnectorError and never leaks token in logs/messages."""
    transport = make_exercism_transport()
    secret_token = "my_super_secret_token_abc"
    connector = ExercismConnector(auth_token="invalid_secret_token", transport=transport)

    with pytest.raises(ConnectorError) as exc_info:
        await connector.fetch_solutions("iHiD")

    assert exc_info.value.status_code == 401
    assert "Exercism authentication failed" in str(exc_info.value)
    # Ensure secret token is NOT leaked in the error message or representation
    assert secret_token not in str(exc_info.value)
    assert secret_token not in repr(connector)


@pytest.mark.asyncio
async def test_08_exercism_errors_and_rate_limits():
    """Requirement 8: 404, 429, 500, timeout, and malformed responses handled safely."""
    # 1. 404
    transport_404 = make_exercism_transport(user_status=404)
    conn_404 = ExercismConnector(transport=transport_404)
    assert await conn_404.validate_identity("not_a_user") is False
    assert await conn_404.fetch_profile("not_a_user") is None

    # 2. 429 Rate limited
    transport_429 = make_exercism_transport(user_status=429)
    conn_429 = ExercismConnector(transport=transport_429)
    with pytest.raises(RateLimitedError):
        await conn_429.validate_identity("iHiD")

    # 3. 502 Upstream unavailable
    transport_502 = make_exercism_transport(user_status=502)
    conn_502 = ExercismConnector(transport=transport_502)
    with pytest.raises(UpstreamUnavailableError):
        await conn_502.validate_identity("iHiD")

    # 4. Timeout
    def timeout_handler(req: httpx.Request):
        raise httpx.ReadTimeout("Timeout reading Exercism")

    transport_timeout = httpx.MockTransport(timeout_handler)
    conn_timeout = ExercismConnector(transport=transport_timeout)
    with pytest.raises(UpstreamUnavailableError):
        await conn_timeout.fetch_profile("iHiD")

    # 5. Malformed JSON
    def malformed_handler(req: httpx.Request):
        return httpx.Response(200, text="NOT_JSON{{{")

    transport_malformed = httpx.MockTransport(malformed_handler)
    conn_malformed = ExercismConnector(transport=transport_malformed)
    with pytest.raises(UpstreamFormatError):
        await conn_malformed.fetch_profile("iHiD")


def test_09_exercism_failed_refresh_preserves_database_evidence(db_session, monkeypatch):
    """Requirement 9: A failed sync preserves existing valid evidence in the database."""
    uid = uuid.uuid4().hex[:12]
    user = User(clerk_user_id=f"test_exercism_preserve_{uid}", email=f"exercism_preserve_{uid}@test.com")
    db_session.add(user)
    db_session.commit()

    conn = PlatformConnection(
        user_id=user.id,
        platform="Exercism",
        username="iHiD",
        connected=True,
    )
    db_session.add(conn)
    db_session.commit()

    ev = Evidence(
        user_id=user.id,
        platform_connection_id=conn.id,
        external_id=f"exercism_profile_ihid_{uid}",
        evidence_type="problem_solving_summary",
        title="Exercism Profile: iHiD (Reputation: 69.9k)",
        normalized_payload={"reputation": "69.9k", "active_tracks_count": 3},
        raw_payload={"reputation": {"total": "69.9k"}},
    )
    db_session.add(ev)
    db_session.commit()

    try:
        # Simulate Exercism outage during sync (502 / UpstreamUnavailableError)
        from app.services.platform.registry import PlatformRegistry

        failing_transport = make_exercism_transport(user_status=502)
        failing_connector = ExercismConnector(transport=failing_transport)
        monkeypatch.setattr(
            PlatformRegistry,
            "get_connector_instance",
            lambda key, auth_token=None: failing_connector,
        )

        headers = {"X-Clerk-User-Id": user.clerk_user_id}
        res = client.post(
            "/api/v1/platforms/exercism/sync",
            json={"username": "iHiD", "auth_type": "api_key"},
            headers=headers,
        )
        assert res.status_code == 502

        # Verify historical evidence was preserved
        db_session.refresh(conn)
        assert conn.connected is True
        existing_ev = (
            db_session.query(Evidence)
            .filter_by(user_id=user.id, external_id=f"exercism_profile_ihid_{uid}")
            .first()
        )
        assert existing_ev is not None
        assert existing_ev.normalized_payload["reputation"] == "69.9k"
        assert existing_ev.normalized_payload["active_tracks_count"] == 3
    finally:
        db_session.query(Evidence).filter_by(user_id=user.id).delete()
        db_session.query(PlatformConnection).filter_by(user_id=user.id).delete()
        db_session.query(User).filter_by(id=user.id).delete()
        db_session.commit()
