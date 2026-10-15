"""Comprehensive regression tests for GeeksforGeeks connector repair (Batch 1).

Covers all Phase 4 requirements:
1. Successful parsing of current App Router / RSC fixture.
2. Successful parsing of legacy __NEXT_DATA__ fixture.
3. Correct extraction and normalization of available profile metrics.
4. Correct handling of missing optional metrics.
5. Correct handling of a genuine numeric zero.
6. Malformed or truncated RSC payload.
7. HTML response with no recognizable profile data.
8. Profile identity mismatch when identity is present.
9. HTTP 404.
10. HTTP 429 (rate limiting).
11. HTTP 5xx or timeout.
12. Failed refresh preserves existing valid database evidence.
"""

import json
import pytest
import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.models.evidence import Evidence
from app.models.platform import PlatformConnection
from app.models.user import User
from app.services.platform.errors import RateLimitedError, UpstreamFormatError, UpstreamUnavailableError
from app.services.platform.geeksforgeeks import (
    GeeksforGeeksConnector,
    extract_app_router_profile,
    extract_next_data,
)

client = TestClient(app)

# --- Fixtures ---

APP_ROUTER_HTML_VALID = """
<!DOCTYPE html>
<html>
<head><title>paji - GeeksforGeeks</title></head>
<body>
<div>Public Profile</div>
<script>
self.__next_f.push([1,"7:{\\"articleCount\\":{\\"name\\":\\"Paji Dev\\",\\"score\\":1086,\\"total_problems_solved\\":329,\\"institute_rank\\":108,\\"institute_name\\":\\"IIT Kanpur\\",\\"monthly_score\\":25,\\"pod_solved_longest_streak\\":400,\\"profile_image_url\\":\\"https://media.geeksforgeeks.org/img-practice/paji.png\\"},\\"mentor\\":{\\"handle\\":\\"paji\\",\\"name\\":\\"Paji Dev\\"},\\"username\\":\\"paji\\",\\"userData\\":{}}"])
</script>
</body>
</html>
"""

APP_ROUTER_HTML_ZERO = """
<!DOCTYPE html>
<html>
<body>
<script>
self.__next_f.push([1,"{\\"articleCount\\":{\\"name\\":\\"Newbie\\",\\"score\\":0,\\"total_problems_solved\\":0,\\"institute_rank\\":null,\\"monthly_score\\":0,\\"pod_solved_longest_streak\\":0},\\"mentor\\":{\\"handle\\":\\"newbie\\"},\\"username\\":\\"newbie\\"}"])
</script>
</body>
</html>
"""

APP_ROUTER_HTML_MISMATCH = """
<!DOCTYPE html>
<html>
<body>
<script>
self.__next_f.push([1,"{\\"articleCount\\":{\\"name\\":\\"Other Dev\\",\\"score\\":500,\\"total_problems_solved\\":100},\\"mentor\\":{\\"handle\\":\\"someone_else\\"},\\"username\\":\\"someone_else\\"}"])
</script>
</body>
</html>
"""

APP_ROUTER_HTML_MALFORMED = """
<!DOCTYPE html>
<html>
<body>
<script>
self.__next_f.push([1,"{\\"articleCount\\":{\\"score\\":1086, total_problems_solved TRUNCATED...
</script>
</body>
</html>
"""

APP_ROUTER_HTML_NO_DATA = """
<!DOCTYPE html>
<html>
<head><title>GeeksforGeeks</title></head>
<body>
<h1>Welcome to GeeksforGeeks</h1>
<p>Some random static content with no profile data.</p>
</body>
</html>
"""

LEGACY_NEXT_DATA_HTML = """
<!DOCTYPE html>
<html>
<head></head>
<body>
<script id="__NEXT_DATA__" type="application/json">
{
  "props": {
    "pageProps": {
      "userInfo": {
        "name": "Legacy User",
        "score": 850,
        "total_problems_solved": 210,
        "institute_rank": 15,
        "institute_name": "NIT",
        "pod_solved_longest_streak": 90,
        "profile_image_url": "https://img.test/pic.png"
      },
      "userSubmissionsInfo": {
        "Easy": {"1": {"pname": "Problem 1", "slug": "problem-1", "lang": "python3"}},
        "Medium": {"2": {"pname": "Problem 2", "slug": "problem-2", "lang": "cpp"}}
      }
    }
  }
}
</script>
</body>
</html>
"""


# --- Test Cases ---

@pytest.mark.asyncio
async def test_1_gfg_app_router_parsing():
    """Case 1: Successful parsing of a current-format App Router/RSC fixture."""
    res = extract_app_router_profile(APP_ROUTER_HTML_VALID, "paji")
    assert res is not None
    prof = res["profile"]
    assert prof["username"] == "paji"
    assert prof["name"] == "Paji Dev"
    assert prof["coding_score"] == 1086
    assert prof["total_solved"] == 329
    assert prof["institute_rank"] == 108
    assert prof["institute"] == "IIT Kanpur"
    assert prof["streak"] == 400
    assert prof["monthly_score"] == 25
    assert prof["avatar_url"] == "https://media.geeksforgeeks.org/img-practice/paji.png"


@pytest.mark.asyncio
async def test_2_gfg_legacy_next_data_parsing():
    """Case 2: Successful parsing of legacy __NEXT_DATA__ fixture."""
    parsed = extract_next_data(LEGACY_NEXT_DATA_HTML)
    assert parsed is not None
    assert "props" in parsed

    transport = httpx.MockTransport(lambda req: httpx.Response(200, text=LEGACY_NEXT_DATA_HTML))
    connector = GeeksforGeeksConnector(transport=transport)
    assert await connector.validate_identity("legacy_user") is True
    prof = await connector.fetch_profile("legacy_user")
    assert prof["name"] == "Legacy User"
    assert prof["coding_score"] == 850
    assert prof["total_solved"] == 210


@pytest.mark.asyncio
async def test_3_gfg_metrics_extraction_and_normalization():
    """Case 3: Correct extraction and normalization of available profile metrics."""
    transport = httpx.MockTransport(lambda req: httpx.Response(200, text=APP_ROUTER_HTML_VALID))
    connector = GeeksforGeeksConnector(transport=transport)
    evidence_list = await connector.fetch_evidence("paji")
    assert len(evidence_list) == 1
    assert evidence_list[0]["type"] == "gfg_profile_stats"

    norm = connector.normalize_evidence(evidence_list[0])
    assert norm["platform"] == "GeeksforGeeks"
    assert norm["evidence_type"] == "problem_solving_summary"
    assert norm["external_id"] == "gfg_profile_paji"
    assert norm["normalized_payload"]["total_solved"] == 329
    assert norm["normalized_payload"]["coding_score"] == 1086
    assert norm["normalized_payload"]["institute_rank"] == 108
    assert "Problem Solving" in norm["normalized_payload"]["skills"]


@pytest.mark.asyncio
async def test_4_gfg_missing_optional_metrics():
    """Case 4: Correct handling of missing optional metrics."""
    html_missing_optional = """
    <html><body><script>
    self.__next_f.push([1,"{\\"articleCount\\":{\\"total_problems_solved\\":50},\\"mentor\\":{\\"handle\\":\\"partial\\"},\\"username\\":\\"partial\\"}"])
    </script></body></html>
    """
    transport = httpx.MockTransport(lambda req: httpx.Response(200, text=html_missing_optional))
    connector = GeeksforGeeksConnector(transport=transport)
    prof = await connector.fetch_profile("partial")
    assert prof is not None
    assert prof["total_solved"] == 50
    assert prof["coding_score"] is None
    assert prof["institute"] is None
    assert prof["institute_rank"] is None
    assert prof["streak"] is None


@pytest.mark.asyncio
async def test_5_gfg_genuine_numeric_zero():
    """Case 5: Correct handling of a genuine numeric zero."""
    transport = httpx.MockTransport(lambda req: httpx.Response(200, text=APP_ROUTER_HTML_ZERO))
    connector = GeeksforGeeksConnector(transport=transport)
    prof = await connector.fetch_profile("newbie")
    assert prof is not None
    assert prof["total_solved"] == 0
    assert prof["coding_score"] == 0
    assert prof["monthly_score"] == 0
    assert prof["streak"] == 0
    assert prof["institute_rank"] is None


@pytest.mark.asyncio
async def test_6_gfg_malformed_rsc_payload():
    """Case 6: Malformed or truncated RSC payload raises UpstreamFormatError."""
    transport = httpx.MockTransport(lambda req: httpx.Response(200, text=APP_ROUTER_HTML_MALFORMED))
    connector = GeeksforGeeksConnector(transport=transport)
    with pytest.raises(UpstreamFormatError):
        await connector.validate_identity("badpayload")


@pytest.mark.asyncio
async def test_7_gfg_html_with_no_recognizable_profile_data():
    """Case 7: HTML response with no recognizable profile data raises UpstreamFormatError."""
    transport = httpx.MockTransport(lambda req: httpx.Response(200, text=APP_ROUTER_HTML_NO_DATA))
    connector = GeeksforGeeksConnector(transport=transport)
    with pytest.raises(UpstreamFormatError):
        await connector.validate_identity("nodata")


@pytest.mark.asyncio
async def test_8_gfg_profile_identity_mismatch():
    """Case 8: Profile identity mismatch when identity is present."""
    transport = httpx.MockTransport(lambda req: httpx.Response(200, text=APP_ROUTER_HTML_MISMATCH))
    connector = GeeksforGeeksConnector(transport=transport)
    # The page belongs to 'someone_else', but we requested 'paji'
    assert await connector.validate_identity("paji") is False
    assert await connector.fetch_profile("paji") is None


@pytest.mark.asyncio
async def test_9_gfg_http_404():
    """Case 9: HTTP 404 returns False / None."""
    transport = httpx.MockTransport(lambda req: httpx.Response(404, text="Not Found"))
    connector = GeeksforGeeksConnector(transport=transport)
    assert await connector.validate_identity("ghost") is False
    assert await connector.fetch_profile("ghost") is None
    assert await connector.fetch_evidence("ghost") == []


@pytest.mark.asyncio
async def test_10_gfg_http_429_rate_limiting():
    """Case 10: HTTP 429 raises RateLimitedError."""
    transport = httpx.MockTransport(lambda req: httpx.Response(429, text="Too Many Requests"))
    connector = GeeksforGeeksConnector(transport=transport)
    with pytest.raises(RateLimitedError):
        await connector.validate_identity("fast")


@pytest.mark.asyncio
async def test_11_gfg_http_5xx_and_timeout():
    """Case 11: HTTP 5xx or timeout raises UpstreamUnavailableError."""
    transport_503 = httpx.MockTransport(lambda req: httpx.Response(503, text="Service Unavailable"))
    with pytest.raises(UpstreamUnavailableError):
        await GeeksforGeeksConnector(transport=transport_503).validate_identity("down")

    def timeout_handler(req):
        raise httpx.ReadTimeout("Timeout reading from socket")

    transport_timeout = httpx.MockTransport(timeout_handler)
    with pytest.raises(UpstreamUnavailableError):
        await GeeksforGeeksConnector(transport=transport_timeout).validate_identity("slow")


def test_12_gfg_failed_refresh_preserves_database_evidence(db_session, monkeypatch):
    """Case 12: A failed refresh does not overwrite or delete existing valid evidence."""
    import uuid
    uid = uuid.uuid4().hex[:12]
    user = User(clerk_user_id=f"test_gfg_preserve_{uid}", email=f"gfg_preserve_{uid}@test.com")
    db_session.add(user)
    db_session.commit()

    conn = PlatformConnection(
        user_id=user.id,
        platform="GeeksforGeeks",
        username="paji",
        connected=True,
    )
    db_session.add(conn)
    db_session.commit()

    ev = Evidence(
        user_id=user.id,
        platform_connection_id=conn.id,
        external_id=f"gfg_profile_paji_{uid}",
        evidence_type="problem_solving_summary",
        title="GeeksforGeeks Profile: paji (329 Solved)",
        normalized_payload={"total_solved": 329, "coding_score": 1086},
        raw_payload={"score": 1086, "total_problems_solved": 329},
    )
    db_session.add(ev)
    db_session.commit()

    try:
        # Now attempt a sync where upstream GFG throws a 502 / UpstreamUnavailableError
        from app.services.platform.registry import PlatformRegistry
        failing_transport = httpx.MockTransport(lambda req: httpx.Response(502))
        failing_connector = GeeksforGeeksConnector(transport=failing_transport)
        monkeypatch.setattr(PlatformRegistry, "get_connector_instance", lambda key, auth_token=None: failing_connector)

        headers = {"X-Clerk-User-Id": user.clerk_user_id}
        res = client.post("/api/v1/platforms/geeksforgeeks/sync", json={"username": "paji"}, headers=headers)
        assert res.status_code == 502

        # Evidence and connection must still be present and intact
        db_session.refresh(conn)
        assert conn.connected is True
        existing_ev = db_session.query(Evidence).filter_by(user_id=user.id, external_id=f"gfg_profile_paji_{uid}").first()
        assert existing_ev is not None
        assert existing_ev.normalized_payload["total_solved"] == 329
        assert existing_ev.normalized_payload["coding_score"] == 1086
    finally:
        db_session.query(Evidence).filter_by(user_id=user.id).delete()
        db_session.query(PlatformConnection).filter_by(user_id=user.id).delete()
        db_session.query(User).filter_by(id=user.id).delete()
        db_session.commit()
