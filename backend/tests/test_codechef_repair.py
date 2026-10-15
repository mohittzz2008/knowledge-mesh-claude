"""Comprehensive regression and repair test suite for CodeChef connector (Batch 4).

Covers:
1. Valid and invalid handles (rejection without network requests).
2. Modern profile HTML parsing (spans, stars glyphs, sidebar ranks, contest count).
3. Legacy / mock profile parsing (direct text, star text, inline links).
4. Unrated user: rating NA, stars None, global_rank None, no star badge.
5. Inactive ranked user: rating present, global_rank None (not 0).
6. Genuine zero total solved problems: verified profile with 0 solved.
7. Total problems solved aggregate header vs list extraction.
8. Contest participation extraction from multiple markup patterns.
9. Non-profile 200 response (e.g. redirect/homepage) fails validation and returns None.
10. Malformed or truncated HTML handled safely.
11. Evidence extraction and deduplication (profile stats, star badge, solved problems).
12. Timestamp integrity (no fabricated dates for problem solutions).
13. HTTP errors, timeouts, rate limits mapped to typed connector errors.
14. Failed refresh preserves previously stored database evidence.
15. Compatibility with platform sync API.
"""

import uuid
from unittest.mock import AsyncMock, patch
import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.evidence import Evidence
from app.models.platform import PlatformConnection
from app.models.user import User
from app.services.platform.codechef import CodeChefConnector, extract_codechef_solved_problems
from app.services.platform.errors import RateLimitedError, UpstreamUnavailableError
from app.services.platform.registry import PlatformRegistry

client = TestClient(app)

# ---------------------------------------------------------------------------
# HTML Fixtures
# ---------------------------------------------------------------------------

MODERN_CODECHEF_HTML = """
<!DOCTYPE html>
<html>
<head><title>errichto - CodeChef User Profile with global rank 8 | CodeChef</title></head>
<body>
  <div class="user-details">
    <h1 class="h2-style">Kamil Debowski</h1>
  </div>
  <aside class="sidebar small-4 columns">
    <div class="rating-header text-center">
      <div class="rating-number">2557</div>
      <small>(Highest Rating 2557)</small>
      <div class="rating-star">
        <span style="background-color:#D0011B">&#9733;</span>
        <span style="background-color:#D0011B">&#9733;</span>
        <span style="background-color:#D0011B">&#9733;</span>
        <span style="background-color:#D0011B">&#9733;</span>
        <span style="background-color:#D0011B">&#9733;</span>
        <span style="background-color:#D0011B">&#9733;</span>
        <span style="background-color:#D0011B">&#9733;</span>
      </div>
    </div>
    <div class="rating-ranks">
      <ul class="inline-list">
        <li>
          <a href="/ratings/all"><strong>8</strong></a>
          Global Rank
        </li>
        <li>
          <a href="/ratings/all?filterBy=Country%3D"><strong>1</strong></a>
          Country Rank
        </li>
      </ul>
    </div>
  </aside>
  <div class="contest-count">
    No. of Contests Participated: <b>18</b>
  </div>
  <section class="rating-data-section problems-solved">
    <h3>Total Problems Solved: 4</h3>
    <div class="content">
      <h5><span>October Challenge 2013</span></h5>
      <p>
        <span>
          <span style="font-size: 12px";>Maxim and Dividers</span>,&nbsp;
          <span style="font-size: 12px";>Helping Lira</span>
        </span>
      </p>
      <p>
        <a href="/problems/FLOW001">FLOW001</a>
        <a href="/status/ATM,errichto">ATM</a>
      </p>
    </div>
  </section>
</body>
</html>
"""

UNRATED_CODECHEF_HTML = """
<!DOCTYPE html>
<html>
<head><title>newbie_coder - CodeChef</title></head>
<body>
  <div class="user-details">
    <h1 class="h2-style">Newbie Coder</h1>
  </div>
  <div class="rating-header">
    <div class="rating-number">NA</div>
    <small>(Highest Rating 0)</small>
  </div>
  <div class="rating-ranks">
    <ul class="inline-list">
      <li><a href="/ratings/all"><strong>Inactive</strong></a> Global Rank</li>
      <li><a href="/ratings/all?filterBy=Country%3D"><strong>Inactive</strong></a> Country Rank</li>
    </ul>
  </div>
  <div class="contest-count">
    Contests Participated: <b>0</b>
  </div>
  <section class="rating-data-section problems-solved">
    <h3>Total Problems Solved: 0</h3>
    <p>None</p>
  </section>
</body>
</html>
"""

INACTIVE_CODECHEF_HTML = """
<!DOCTYPE html>
<html>
<head><title>retired_master - CodeChef</title></head>
<body>
  <div class="user-details">
    <h1 class="h2-style">Retired Master</h1>
  </div>
  <div class="rating-header">
    <div class="rating-number">2150</div>
    <small>(Highest Rating 2300)</small>
    <div class="rating-star">5★</div>
  </div>
  <div class="rating-ranks">
    <ul class="inline-list">
      <li><a href="/ratings/all"><strong>Inactive</strong></a> Global Rank</li>
      <li><a href="/ratings/all?filterBy=Country%3D"><strong>Inactive</strong></a> Country Rank</li>
    </ul>
  </div>
  <div class="contest-count">
    Contests Participated: <b>42</b>
  </div>
  <section class="rating-data-section problems-solved">
    <h3>Total Problems Solved: 85</h3>
  </section>
</body>
</html>
"""

NOT_A_PROFILE_HTML = """
<!DOCTYPE html>
<html>
<head><title>CodeChef | Competitive Programming</title></head>
<body>
  <h1>Page Not Found</h1>
  <p>The requested user ghost_user could not be found.</p>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Unit Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_codechef_rejects_unsafe_handles():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, text=MODERN_CODECHEF_HTML)

    connector = CodeChefConnector(transport=httpx.MockTransport(handler))
    for bad in ["", "   ", "../etc/passwd", "user/name", "a b", "x?y=1", "a" * 70]:
        assert await connector.validate_identity(bad) is False
        assert await connector.fetch_profile(bad) is None
        assert await connector.fetch_evidence(bad) == []
    assert calls == []


@pytest.mark.asyncio
async def test_codechef_modern_profile_parsing():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=MODERN_CODECHEF_HTML)

    connector = CodeChefConnector(transport=httpx.MockTransport(handler))
    assert await connector.validate_identity("errichto") is True

    profile = await connector.fetch_profile("errichto")
    assert profile is not None
    assert profile["username"] == "errichto"
    assert profile["name"] == "Kamil Debowski"
    assert profile["rating"] == 2557
    assert profile["highest_rating"] == 2557
    assert profile["stars"] == "7★"
    assert profile["global_rank"] == 8
    assert profile["country_rank"] == 1
    assert profile["contests_participated"] == 18
    assert profile["total_solved"] == 4
    assert len(profile["solved_problems"]) == 4
    codes = set(profile["solved_codes"])
    assert "FLOW001" in codes
    assert "ATM" in codes
    assert "MAXIMANDDIVIDERS" in codes
    assert "HELPINGLIRA" in codes


@pytest.mark.asyncio
async def test_codechef_unrated_user_distinguishes_zero_from_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=UNRATED_CODECHEF_HTML)

    connector = CodeChefConnector(transport=httpx.MockTransport(handler))
    assert await connector.validate_identity("newbie_coder") is True

    profile = await connector.fetch_profile("newbie_coder")
    assert profile is not None
    assert profile["rating"] is None
    assert profile["highest_rating"] is None
    assert profile["stars"] is None
    assert profile["global_rank"] is None
    assert profile["country_rank"] is None
    assert profile["contests_participated"] == 0
    assert profile["total_solved"] == 0
    assert profile["solved_problems"] == []

    evidence = await connector.fetch_evidence("newbie_coder")
    # Only profile_stats, NO fabricated star badge
    badge_items = [e for e in evidence if e["type"] == "codechef_star_badge"]
    assert len(badge_items) == 0

    stat_item = [e for e in evidence if e["type"] == "codechef_profile_stats"][0]
    norm = connector.normalize_evidence(stat_item)
    assert norm["normalized_payload"]["rating"] is None
    assert norm["normalized_payload"]["stars"] is None
    assert norm["normalized_payload"]["skills"] == []


@pytest.mark.asyncio
async def test_codechef_inactive_user_preserves_none_for_ranks():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=INACTIVE_CODECHEF_HTML)

    connector = CodeChefConnector(transport=httpx.MockTransport(handler))
    profile = await connector.fetch_profile("retired_master")
    assert profile is not None
    assert profile["rating"] == 2150
    assert profile["highest_rating"] == 2300
    assert profile["stars"] == "5★"
    assert profile["global_rank"] is None  # 'Inactive' -> None, not 0
    assert profile["country_rank"] is None
    assert profile["contests_participated"] == 42
    assert profile["total_solved"] == 85


@pytest.mark.asyncio
async def test_codechef_non_profile_200_returns_none():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=NOT_A_PROFILE_HTML)

    connector = CodeChefConnector(transport=httpx.MockTransport(handler))
    assert await connector.validate_identity("ghost_user") is False
    assert await connector.fetch_profile("ghost_user") is None
    assert await connector.fetch_evidence("ghost_user") == []


@pytest.mark.asyncio
async def test_codechef_malformed_html_handles_safely():
    connector = CodeChefConnector()
    # Empty string
    assert extract_codechef_solved_problems("") == []

    # Malformed section with no matching problems
    assert extract_codechef_solved_problems("<section class='problems-solved'><div class='broken'") == []

    # Profile with broken numbers
    broken_html = """
    <html><head><title>broken - CodeChef</title></head><body>
      <div class="rating-header"><div class="rating-number">NaN</div>
      <div class="rating-star">invalid</div></div>
      <div class="rating-ranks"><strong>??</strong> Global Rank</div>
      <section class="problems-solved"><h3>Total Problems Solved: not_a_num</h3></section>
    </body></html>
    """
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=broken_html)

    c = CodeChefConnector(transport=httpx.MockTransport(handler))
    prof = await c.fetch_profile("broken")
    assert prof is not None
    assert prof["rating"] is None
    assert prof["global_rank"] is None
    assert prof["total_solved"] == 0


@pytest.mark.asyncio
async def test_codechef_evidence_normalization_and_timestamps():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=MODERN_CODECHEF_HTML)

    connector = CodeChefConnector(transport=httpx.MockTransport(handler))
    items = await connector.fetch_evidence("errichto")
    assert len(items) == 6  # 1 profile + 1 badge + 4 problems

    for item in items:
        norm = connector.normalize_evidence(item)
        assert norm["platform"] == "CodeChef"
        if item["type"] == "codechef_profile_stats":
            assert norm["evidence_type"] == "problem_solving_summary"
            assert norm["normalized_payload"]["rating"] == 2557
            assert norm["normalized_payload"]["global_rank"] == 8
            assert norm["normalized_payload"]["country_rank"] == 1
            assert norm["normalized_payload"]["contests_participated"] == 18
            assert "Competitive Programming" in norm["normalized_payload"]["skills"]
        elif item["type"] == "codechef_star_badge":
            assert norm["evidence_type"] == "badge"
            assert norm["normalized_payload"]["stars"] == 7
            assert norm["occurred_at"] is None  # no fabricated badge date
        elif item["type"] == "codechef_solved_problem":
            assert norm["evidence_type"] == "problem_submission"
            assert norm["occurred_at"] is None  # no fabricated solve date
            assert norm["normalized_payload"]["passed"] is True


@pytest.mark.asyncio
async def test_codechef_upstream_http_errors():
    def handler_429(request):
        return httpx.Response(429)

    with pytest.raises(RateLimitedError):
        await CodeChefConnector(transport=httpx.MockTransport(handler_429)).validate_identity("chef")

    def handler_503(request):
        return httpx.Response(503)

    with pytest.raises(UpstreamUnavailableError):
        await CodeChefConnector(transport=httpx.MockTransport(handler_503)).validate_identity("chef")

    def handler_timeout(request):
        raise httpx.ReadTimeout("timed out")

    with pytest.raises(UpstreamUnavailableError):
        await CodeChefConnector(transport=httpx.MockTransport(handler_timeout)).validate_identity("chef")


# ---------------------------------------------------------------------------
# Integration & Database Persistence Tests
# ---------------------------------------------------------------------------

def test_codechef_full_sync_and_failed_refresh_preserves_evidence(monkeypatch, db_session):
    user_id = f"test_cc_{uuid.uuid4().hex[:10]}"
    headers = {"X-Clerk-User-Id": user_id}

    state = {"status": 200}

    def transport_handler(request: httpx.Request) -> httpx.Response:
        if state["status"] == 200:
            return httpx.Response(200, text=MODERN_CODECHEF_HTML)
        elif state["status"] == 502:
            return httpx.Response(502)
        return httpx.Response(404)

    mock_transport = httpx.MockTransport(transport_handler)

    original_get_connector = PlatformRegistry.get_connector_instance

    def fake_get_connector(key, auth_token=None):
        if key.lower() == "codechef":
            return CodeChefConnector(transport=mock_transport)
        return original_get_connector(key, auth_token=auth_token)

    monkeypatch.setattr(PlatformRegistry, "get_connector_instance", staticmethod(fake_get_connector))

    # 1. Initial successful sync
    res = client.post("/api/v1/platforms/codechef/sync", json={"username": "errichto"}, headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["platform"] == "CodeChef"
    assert body["synced_evidence_count"] == 6  # 1 profile + 1 badge + 4 problems

    user = db_session.query(User).filter_by(clerk_user_id=user_id).first()
    assert user is not None
    conn = db_session.query(PlatformConnection).filter_by(user_id=user.id, platform="CodeChef").first()
    assert conn is not None and conn.connected is True
    evidence_count = db_session.query(Evidence).filter_by(platform_connection_id=conn.id).count()
    assert evidence_count == 6

    # 2. Subsequent failed refresh (upstream 502)
    state["status"] = 502
    res_failed = client.post("/api/v1/platforms/codechef/sync", json={"username": "errichto"}, headers=headers)
    assert res_failed.status_code == 502

    # Evidence MUST be preserved in full
    evidence_after_failure = db_session.query(Evidence).filter_by(platform_connection_id=conn.id).count()
    assert evidence_after_failure == 6
    conn_after_failure = db_session.query(PlatformConnection).filter_by(id=conn.id).first()
    assert conn_after_failure.connected is True


@pytest.mark.asyncio
async def test_codechef_missing_count_markup_with_partial_list_returns_unknown():
    """Prove that when explicit 'Total Problems Solved: N' markup is absent,
    a partial list of solved problems on the profile page does not masquerade
    as a complete lifetime total, and returns None (established unknown representation).
    """
    partial_html_no_count = """
    <!DOCTYPE html>
    <html>
    <head><title>partial_user - CodeChef</title></head>
    <body>
      <div class="user-details"><h1 class="h2-style">Partial User</h1></div>
      <div class="rating-header">
        <div class="rating-number">1750</div>
        <div class="rating-star">3★</div>
      </div>
      <section class="rating-data-section problems-solved">
        <!-- Explicit 'Total Problems Solved: N' header is missing here -->
        <div class="content">
          <p>
            <span>
              <span style="font-size: 12px";>Problem Alpha</span>,&nbsp;
              <span style="font-size: 12px";>Problem Beta</span>
            </span>
          </p>
        </div>
      </section>
    </body>
    </html>
    """
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=partial_html_no_count)

    c = CodeChefConnector(transport=httpx.MockTransport(handler))
    profile = await c.fetch_profile("partial_user")
    assert profile is not None
    # 2 problems were parsed from the page...
    assert len(profile["solved_problems"]) == 2
    # ...but total_solved MUST be None because the list is partial and explicit total is missing!
    assert profile["total_solved"] is None

    evidence = await c.fetch_evidence("partial_user")
    prof_stat = [e for e in evidence if e["type"] == "codechef_profile_stats"][0]
    norm = c.normalize_evidence(prof_stat)
    assert norm["normalized_payload"]["total_solved"] is None


def test_codechef_rate_limit_429_preserves_evidence_and_subsequent_retry_succeeds(monkeypatch, db_session):
    """Confirm that an HTTP 429 rate-limit failure preserves existing database evidence
    and connection state, and a subsequent successful retry can sync normally.
    """
    user_id = f"test_cc_429_{uuid.uuid4().hex[:10]}"
    headers = {"X-Clerk-User-Id": user_id}

    state = {"status": 200}

    def transport_handler(request: httpx.Request) -> httpx.Response:
        if state["status"] == 200:
            return httpx.Response(200, text=MODERN_CODECHEF_HTML)
        elif state["status"] == 429:
            return httpx.Response(429)
        return httpx.Response(404)

    mock_transport = httpx.MockTransport(transport_handler)

    original_get_connector = PlatformRegistry.get_connector_instance

    def fake_get_connector(key, auth_token=None):
        if key.lower() == "codechef":
            return CodeChefConnector(transport=mock_transport)
        return original_get_connector(key, auth_token=auth_token)

    monkeypatch.setattr(PlatformRegistry, "get_connector_instance", staticmethod(fake_get_connector))

    # 1. Initial successful sync
    res = client.post("/api/v1/platforms/codechef/sync", json={"username": "errichto"}, headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["synced_evidence_count"] == 6

    user = db_session.query(User).filter_by(clerk_user_id=user_id).first()
    assert user is not None
    conn = db_session.query(PlatformConnection).filter_by(user_id=user.id, platform="CodeChef").first()
    assert conn is not None and conn.connected is True
    evidence_count = db_session.query(Evidence).filter_by(platform_connection_id=conn.id).count()
    assert evidence_count == 6

    # 2. Rate-limit failure (HTTP 429)
    state["status"] = 429
    res_429 = client.post("/api/v1/platforms/codechef/sync", json={"username": "errichto"}, headers=headers)
    assert res_429.status_code == 429

    # Evidence and connection state MUST remain intact
    evidence_after_429 = db_session.query(Evidence).filter_by(platform_connection_id=conn.id).count()
    assert evidence_after_429 == 6
    conn_after_429 = db_session.query(PlatformConnection).filter_by(id=conn.id).first()
    assert conn_after_429.connected is True

    # 3. Subsequent successful retry
    state["status"] = 200
    res_retry = client.post("/api/v1/platforms/codechef/sync", json={"username": "errichto"}, headers=headers)
    assert res_retry.status_code == 200
    body_retry = res_retry.json()
    assert body_retry["synced_evidence_count"] == 0
    assert body_retry["updated_evidence_count"] == 6

    # Evidence rows refreshed without duplication
    evidence_after_retry = db_session.query(Evidence).filter_by(platform_connection_id=conn.id).count()
    assert evidence_after_retry == 6
    conn_after_retry = db_session.query(PlatformConnection).filter_by(id=conn.id).first()
    assert conn_after_retry.connected is True

