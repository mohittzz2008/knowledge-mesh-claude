"""Codewars + GeeksforGeeks (and CodeChef hardening) connectors, end to end, with no real network.

Upstream responses are served by httpx.MockTransport, shaped after the documented
Codewars API v1 (https://dev.codewars.com) and the GeeksforGeeks profile page's
embedded __NEXT_DATA__ payload.
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
from app.services.mesh.graph_builder import KnowledgeMeshGraphBuilder
from app.services.mesh.unified_profile import UnifiedProfileService
from app.services.platform import external_platform_names
from app.services.platform.codechef import CodeChefConnector
from app.services.platform.codewars import CodewarsConnector
from app.services.platform.errors import (
    RateLimitedError,
    UpstreamFormatError,
    UpstreamUnavailableError,
)
from app.services.platform.geeksforgeeks import GeeksforGeeksConnector
from app.services.platform.registry import PlatformRegistry

client = TestClient(app)

# --------------------------------------------------------------------------- Codewars fixtures

CW_STATE = {"total_completed": 3}


def cw_user():
    return {
        "username": "JHoffner",
        "name": "Jake Hoffner",
        "honor": 1234,
        "clan": "KM",
        "leaderboardPosition": 99,
        "skills": ["python"],
        "ranks": {
            "overall": {"rank": -4, "name": "4 kyu", "color": "blue", "score": 1600},
            "languages": {
                "python": {"rank": -4, "name": "4 kyu", "color": "blue", "score": 1500},
                "javascript": {"rank": -6, "name": "6 kyu", "color": "yellow", "score": 300},
            },
        },
        "codeChallenges": {"totalAuthored": 1, "totalCompleted": CW_STATE["total_completed"]},
    }


CW_COMPLETED = {
    0: {
        "totalPages": 2,
        "totalItems": 3,
        "data": [
            {"id": "k1", "name": "Multiples of 3 and 5", "slug": "multiples-of-3-and-5",
             "completedAt": "2024-03-01T10:00:00Z", "completedLanguages": ["python", "javascript"]},
            {"id": "k2", "name": "Valid Braces", "slug": "valid-braces",
             "completedAt": "2024-05-01T10:00:00Z", "completedLanguages": ["python"]},
        ],
    },
    1: {
        "totalPages": 2,
        "totalItems": 3,
        "data": [
            {"id": "k3", "name": "Fibonacci", "slug": "fibonacci-fast",
             "completedAt": "2023-01-01T10:00:00Z", "completedLanguages": ["c"]},
        ],
    },
}

CW_DETAILS = {
    "valid-braces": {"slug": "valid-braces", "tags": ["Algorithms", "Recursion", "Strings"],
                     "rank": {"id": -4, "name": "4 kyu", "color": "blue"}},
    "multiples-of-3-and-5": {"slug": "multiples-of-3-and-5", "tags": ["Fundamentals", "Mathematics"],
                             "rank": {"id": -6, "name": "6 kyu", "color": "yellow"}},
    # fibonacci-fast intentionally missing -> 500: enrichment must tolerate it
}


def make_cw_transport(calls=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(request.url.path)
        path = request.url.path
        if path.lower() == "/api/v1/users/jhoffner":  # Codewars usernames are case-insensitive
            return httpx.Response(200, json=cw_user())
        if path == "/api/v1/users/someid123":  # API resolves ids -> returns a different username
            return httpx.Response(200, json=cw_user())
        if path == "/api/v1/users/ghost":
            return httpx.Response(404, json={"success": False, "reason": "not found"})
        if path == "/api/v1/users/slowdown":
            return httpx.Response(429)
        if path == "/api/v1/users/maintenance":
            return httpx.Response(503)
        if path.endswith("/code-challenges/completed"):
            return httpx.Response(200, json=CW_COMPLETED[int(request.url.params.get("page", 0))])
        if path.startswith("/api/v1/code-challenges/"):
            slug = path.rsplit("/", 1)[1]
            if slug in CW_DETAILS:
                return httpx.Response(200, json=CW_DETAILS[slug])
            return httpx.Response(500)
        return httpx.Response(404)

    return httpx.MockTransport(handler)


# --------------------------------------------------------------------------- GFG fixtures


def gfg_html(user_info, submissions=None, *, next_data=True):
    if not next_data:
        return "<html><body><h1>Profile</h1></body></html>"
    data = {"props": {"pageProps": {"userInfo": user_info, "userSubmissionsInfo": submissions or {}}}}
    return (
        '<html><head></head><body><script id="__NEXT_DATA__" type="application/json">'
        + json.dumps(data)
        + "</script></body></html>"
    )


GFG_USER = {
    "name": "Paji Dev",
    "institute_name": "IIT Kanpur",
    "institute_rank": 43,
    "score": 1086,
    "total_problems_solved": 335,
    "monthly_score": 12,
    "pod_solved_longest_streak": 706,
    "profile_image_url": "https://media.geeksforgeeks.org/img-practice/x.png",
}
GFG_SUBMISSIONS = {
    "Easy": {
        "1": {"pname": "Remove Spaces", "slug": "remove-spaces", "lang": "python3"},
        "2": {"pname": "Binary String", "slug": "binary-string", "lang": "python3"},
    },
    "Medium": {"3": {"pname": "Trapping Rain Water", "slug": "trapping-rain-water", "lang": "cpp"}},
    "Hard": {"4": {"pname": "Tic Tac Toe", "slug": "tic-tac-toe", "lang": "python3"}},
}


def make_gfg_transport(calls=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(request.url.path)
        path = request.url.path.lower()
        if path == "/user/paji/":
            return httpx.Response(200, text=gfg_html(GFG_USER, GFG_SUBMISSIONS))
        if path == "/user/ghost/":
            return httpx.Response(404, text="not found")
        if path == "/user/nodata/":
            return httpx.Response(200, text=gfg_html(None, next_data=False))
        if path == "/user/private/":  # page renders, but without any profile
            return httpx.Response(200, text=gfg_html({}))
        if path == "/user/limited/":
            return httpx.Response(429)
        return httpx.Response(404)

    return httpx.MockTransport(handler)


# --------------------------------------------------------------------------- CodeChef fixtures

CC_PROFILE_HTML = """
<html><head><title>demo_chef - CodeChef</title></head><body>
  <h1 class="h2-style">Demo Chef</h1>
  <div class="rating-header"><div class="rating-number">1850</div>
    <small>(Highest Rating 1920)</small><div class="rating-star">4★</div></div>
  <section class="rating-data-section problems-solved">
    <h3>Total Problems Solved: 2</h3>
    <p><span><span style="font-size: 12px";>Jawbreaker</span>,&nbsp;<span style="font-size: 12px";>Closest Ranking</span></span></p>
  </section>
</body></html>
"""
# 200 status, but not a profile (what a "not found" / redirect-to-home page can look like)
CC_NOT_A_PROFILE_HTML = "<html><head><title>CodeChef</title></head><body>Welcome. No such user ghost_chef.</body></html>"


def make_cc_transport(calls=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(request.url.path)
        path = request.url.path.lower()
        if path == "/users/demo_chef":
            return httpx.Response(200, text=CC_PROFILE_HTML)
        if path == "/users/ghost_chef":
            return httpx.Response(200, text=CC_NOT_A_PROFILE_HTML)
        if path == "/users/blocked":
            return httpx.Response(429)
        return httpx.Response(404)

    return httpx.MockTransport(handler)


# --------------------------------------------------------------------------- registry


def test_registry_includes_all_platforms_and_feeds_the_mesh():
    keys = {item.key for item in PlatformRegistry.list_items()}
    assert {"codewars", "geeksforgeeks", "codechef"} <= keys
    names = external_platform_names()
    assert {"Codewars", "GeeksforGeeks", "CodeChef", "Codeforces", "AtCoder", "Exercism"} <= names

    gfg = PlatformRegistry.get_item("geeksforgeeks")
    assert gfg.status == "LIMITED"  # honest: no official API
    assert PlatformRegistry.get_item("codewars").status == "AVAILABLE"


# --------------------------------------------------------------------------- Codewars connector


@pytest.mark.asyncio
async def test_codewars_validate_identity():
    c = CodewarsConnector(transport=make_cw_transport())
    assert await c.validate_identity("jhoffner") is True  # case-insensitive match
    assert await CodewarsConnector(transport=make_cw_transport()).validate_identity("ghost") is False
    # An ID that resolves to a different username must not validate as "that username".
    assert await CodewarsConnector(transport=make_cw_transport()).validate_identity("someid123") is False


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", ["", "   ", "../etc/passwd", "a/b", "x?y=1", "name with space", "a" * 80])
async def test_codewars_rejects_unsafe_handles_without_any_request(bad):
    calls = []
    c = CodewarsConnector(transport=make_cw_transport(calls))
    assert await c.validate_identity(bad) is False
    assert await c.fetch_profile(bad) is None
    assert await c.fetch_evidence(bad) == []
    assert calls == []


@pytest.mark.asyncio
async def test_codewars_upstream_failures_raise_typed_errors_not_not_found():
    with pytest.raises(RateLimitedError):
        await CodewarsConnector(transport=make_cw_transport()).validate_identity("slowdown")
    with pytest.raises(UpstreamUnavailableError):
        await CodewarsConnector(transport=make_cw_transport()).validate_identity("maintenance")


@pytest.mark.asyncio
async def test_codewars_network_failure_is_typed():
    def boom(request):
        raise httpx.ConnectError("no route")

    c = CodewarsConnector(transport=httpx.MockTransport(boom))
    with pytest.raises(UpstreamUnavailableError):
        await c.validate_identity("jhoffner")


@pytest.mark.asyncio
async def test_codewars_profile():
    CW_STATE["total_completed"] = 3
    p = await CodewarsConnector(transport=make_cw_transport()).fetch_profile("jhoffner")
    assert p["username"] == "JHoffner"
    assert p["total_solved"] == 3
    assert p["honor"] == 1234
    assert p["rank_name"] == "4 kyu"
    assert p["language_ranks"]["python"]["score"] == 1500
    assert p["html_url"] == "https://www.codewars.com/users/JHoffner"


@pytest.mark.asyncio
async def test_codewars_evidence_paginates_sorts_and_tolerates_failed_detail_lookups():
    CW_STATE["total_completed"] = 3
    calls = []
    c = CodewarsConnector(transport=make_cw_transport(calls))
    items = await c.fetch_evidence("jhoffner")

    assert items[0]["type"] == "codewars_profile_stats"
    katas = [i for i in items if i["type"] == "codewars_kata"]
    assert [k["data"]["id"] for k in katas] == ["k2", "k1", "k3"]  # newest first, both pages read
    assert sum(1 for p in calls if p.endswith("/completed")) == 2
    assert calls.count("/api/v1/users/jhoffner") == 1  # profile fetched once, never per kata

    norm = {i["data"]["id"]: c.normalize_evidence(i) for i in katas}
    assert "Recursion" in norm["k2"]["normalized_payload"]["skills"]
    assert "Python" in norm["k2"]["normalized_payload"]["skills"]
    assert norm["k2"]["normalized_payload"]["difficulty"] == "4 kyu"
    assert norm["k2"]["title"].endswith("(4 kyu)")
    # k3's detail lookup returned 500: still ingested, just without tags
    assert norm["k3"]["normalized_payload"]["tags"] == []
    assert "C" in norm["k3"]["normalized_payload"]["skills"]
    assert norm["k2"]["evidence_type"] == "problem_submission"
    assert norm["k2"]["normalized_payload"]["passed"] is True
    assert norm["k2"]["occurred_at"] == "2024-05-01T10:00:00Z"
    assert norm["k2"]["source_url"] == "https://www.codewars.com/kata/valid-braces"


@pytest.mark.asyncio
async def test_codewars_profile_normalization():
    c = CodewarsConnector(transport=make_cw_transport())
    items = await c.fetch_evidence("jhoffner")
    n = c.normalize_evidence(items[0])
    assert n["external_id"] == "codewars_profile_jhoffner"
    assert n["evidence_type"] == "problem_solving_summary"
    assert n["normalized_payload"]["total_solved"] == 3
    assert n["normalized_payload"]["skills"][0] == "Python"  # most-used language first
    assert "Problem Solving" in n["normalized_payload"]["skills"]
    assert c.normalize_evidence({"type": "something_else"}) == {}


# --------------------------------------------------------------------------- GFG connector


@pytest.mark.asyncio
async def test_gfg_validate_and_profile():
    c = GeeksforGeeksConnector(transport=make_gfg_transport())
    assert await c.validate_identity("paji") is True
    p = await c.fetch_profile("paji")
    assert p["name"] == "Paji Dev"
    assert p["total_solved"] == 335
    assert p["coding_score"] == 1086
    assert p["institute_rank"] == 43
    assert p["streak"] == 706
    assert p["html_url"] == "https://www.geeksforgeeks.org/user/paji/"


@pytest.mark.asyncio
async def test_gfg_unknown_user_is_not_found_but_layout_change_is_an_error():
    assert await GeeksforGeeksConnector(transport=make_gfg_transport()).validate_identity("ghost") is False
    assert await GeeksforGeeksConnector(transport=make_gfg_transport()).validate_identity("private") is False
    # Page loads but has no embedded data at all: that is OUR problem, never "user not found".
    with pytest.raises(UpstreamFormatError):
        await GeeksforGeeksConnector(transport=make_gfg_transport()).validate_identity("nodata")
    with pytest.raises(RateLimitedError):
        await GeeksforGeeksConnector(transport=make_gfg_transport()).validate_identity("limited")


@pytest.mark.asyncio
async def test_gfg_fetches_the_profile_page_once_per_sync():
    calls = []
    c = GeeksforGeeksConnector(transport=make_gfg_transport(calls))
    await c.validate_identity("paji")
    await c.fetch_profile("paji")
    await c.fetch_evidence("paji")
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_gfg_rejects_unsafe_handles_without_any_request():
    calls = []
    c = GeeksforGeeksConnector(transport=make_gfg_transport(calls))
    for bad in ["", "../x", "a b", "x/y"]:
        assert await c.validate_identity(bad) is False
    assert calls == []


@pytest.mark.asyncio
async def test_gfg_evidence_and_normalization():
    c = GeeksforGeeksConnector(transport=make_gfg_transport())
    items = await c.fetch_evidence("paji")
    assert items[0]["type"] == "gfg_profile_stats"
    problems = [i for i in items if i["type"] == "gfg_problem"]
    assert len(problems) == 4
    assert problems[0]["data"]["difficulty"] == "Hard"  # hardest first

    prof = c.normalize_evidence(items[0])
    assert prof["external_id"] == "gfg_profile_paji"
    assert prof["evidence_type"] == "problem_solving_summary"
    assert prof["normalized_payload"]["difficulty_counts"] == {"Hard": 1, "Medium": 1, "Easy": 2}
    assert prof["normalized_payload"]["skills"][0] == "Python"  # python3 normalised and most used

    prob = c.normalize_evidence(problems[0])
    assert prob["evidence_type"] == "problem_submission"
    assert prob["occurred_at"] is None  # GFG exposes no timestamps; never faked
    assert prob["source_url"] == "https://www.geeksforgeeks.org/problems/tic-tac-toe"
    assert prob["normalized_payload"]["passed"] is True
    assert "Python" in prob["normalized_payload"]["skills"]


# --------------------------------------------------------------------------- CodeChef hardening


@pytest.mark.asyncio
async def test_codechef_does_not_accept_a_non_profile_200_page():
    """Regression: any 200 page containing the username used to validate as a real user."""
    c = CodeChefConnector(transport=make_cc_transport())
    assert await c.validate_identity("ghost_chef") is False
    assert await CodeChefConnector(transport=make_cc_transport()).validate_identity("demo_chef") is True


@pytest.mark.asyncio
async def test_codechef_outage_is_an_error_not_user_not_found():
    with pytest.raises(RateLimitedError):
        await CodeChefConnector(transport=make_cc_transport()).validate_identity("blocked")

    def boom(request):
        raise httpx.ConnectError("no route")

    with pytest.raises(UpstreamUnavailableError):
        await CodeChefConnector(transport=httpx.MockTransport(boom)).validate_identity("demo_chef")


@pytest.mark.asyncio
async def test_codechef_unsafe_handles_never_hit_the_network_and_one_page_per_sync():
    calls = []
    c = CodeChefConnector(transport=make_cc_transport(calls))
    for bad in ["../x", "a/b", "", "x y"]:
        assert await c.validate_identity(bad) is False
    assert calls == []

    await c.validate_identity("demo_chef")
    await c.fetch_profile("demo_chef")
    items = await c.fetch_evidence("demo_chef")
    assert len(calls) == 1
    problems = [c.normalize_evidence(i) for i in items if i["type"] == "codechef_solved_problem"]
    assert problems and all(p["occurred_at"] is None for p in problems)  # no fabricated dates


# --------------------------------------------------------------------------- full API flow


@pytest.fixture()
def wired_connectors(monkeypatch):
    """Route registry lookups for these platforms to mocked transports."""
    original = PlatformRegistry.get_connector_instance

    def fake(key, auth_token=None):
        if key.lower() == "codewars":
            return CodewarsConnector(transport=make_cw_transport())
        if key.lower() == "geeksforgeeks":
            return GeeksforGeeksConnector(transport=make_gfg_transport())
        if key.lower() == "codechef":
            return CodeChefConnector(transport=make_cc_transport())
        return original(key, auth_token=auth_token)

    monkeypatch.setattr(PlatformRegistry, "get_connector_instance", staticmethod(fake))
    CW_STATE["total_completed"] = 3


def new_user_headers():
    return {"X-Clerk-User-Id": f"test_{uuid.uuid4().hex[:12]}"}


def db_user(db, headers):
    return db.query(User).filter(User.clerk_user_id == headers["X-Clerk-User-Id"]).first()


def test_platform_list_shows_new_platforms(wired_connectors):
    headers = new_user_headers()
    res = client.get("/api/v1/platforms", headers=headers)
    assert res.status_code == 200
    by_key = {p["key"]: p for p in res.json()}
    assert by_key["codewars"]["connected"] is False
    assert by_key["geeksforgeeks"]["status"] == "LIMITED"
    assert "codechef" in by_key


def test_codewars_validate_endpoint(wired_connectors):
    headers = new_user_headers()
    ok = client.post("/api/v1/platforms/codewars/validate", json={"username": "jhoffner"}, headers=headers)
    assert ok.status_code == 200 and ok.json()["valid"] is True and ok.json()["total_solved"] == 3
    missing = client.post("/api/v1/platforms/codewars/validate", json={"username": "ghost"}, headers=headers)
    assert missing.status_code == 200 and missing.json()["valid"] is False


def test_validate_requires_authentication(wired_connectors):
    res = client.post("/api/v1/platforms/codewars/validate", json={"username": "jhoffner"})
    assert res.status_code == 401


def test_unknown_platform_is_404(wired_connectors):
    res = client.post("/api/v1/platforms/nope/sync", json={"username": "x"}, headers=new_user_headers())
    assert res.status_code == 404


def test_upstream_failures_map_to_precise_status_codes(wired_connectors):
    h = new_user_headers()
    rate = client.post("/api/v1/platforms/codewars/sync", json={"username": "slowdown"}, headers=h)
    assert rate.status_code == 429
    down = client.post("/api/v1/platforms/codewars/sync", json={"username": "maintenance"}, headers=h)
    assert down.status_code == 502
    layout = client.post("/api/v1/platforms/geeksforgeeks/validate", json={"username": "nodata"}, headers=h)
    assert layout.status_code == 502 and "layout" in layout.json()["detail"].lower()
    nf = client.post("/api/v1/platforms/codewars/sync", json={"username": "ghost"}, headers=h)
    assert nf.status_code == 404
    cc = client.post("/api/v1/platforms/codechef/sync", json={"username": "blocked"}, headers=h)
    assert cc.status_code == 429


def test_failed_sync_leaves_no_phantom_connection(wired_connectors, db_session):
    """Regression: the connection used to be saved as 'connected' before the fetch could fail."""
    h = new_user_headers()
    assert client.post("/api/v1/platforms/codewars/sync", json={"username": "maintenance"}, headers=h).status_code == 502
    assert client.post("/api/v1/platforms/codewars/sync", json={"username": "ghost"}, headers=h).status_code == 404
    user = db_user(db_session, h)
    assert db_session.query(PlatformConnection).filter_by(user_id=user.id).count() == 0
    listing = {p["key"]: p for p in client.get("/api/v1/platforms", headers=h).json()}
    assert listing["codewars"]["connected"] is False


def test_codewars_full_sync_feeds_mesh_profile_and_graph(wired_connectors, db_session):
    h = new_user_headers()
    res = client.post("/api/v1/platforms/codewars/sync", json={"username": "jhoffner"}, headers=h)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["platform"] == "Codewars"
    assert body["synced_evidence_count"] == 4  # profile + 3 kata
    assert body["profile_summary"]["total_solved"] == 3
    labels = {x["label"]: x["value"] for x in body["profile_summary"]["highlights"]}
    assert labels["Rank"] == "4 kyu" and labels["Honor"] == 1234

    user = db_user(db_session, h)
    profile = UnifiedProfileService().get_unified_profile(user.id, db_session)
    assert profile["platform_counts"]["Codewars"] == 4  # not mis-bucketed as CodeLab
    summary = {c["platform"]: c for c in profile["connected_platforms"]}
    assert summary["Codewars"]["connected"] is True and summary["Codewars"]["username"] == "jhoffner"
    assert summary["GeeksforGeeks"]["connected"] is False

    skills = {s["slug"]: s for s in profile["skills"]}
    for slug in ("python", "recursion", "problem-solving", "c"):
        assert skills[slug]["status"] != "NO_EVIDENCE", slug
        assert skills[slug]["sources"]["Codewars"] >= 1, slug
    assert skills["recursion"]["sources"]["GitHub"] == 0

    graph = KnowledgeMeshGraphBuilder().build_graph(user.id, db_session)
    assert graph["total_skills"] > 0

    # Disconnect drops it from the mesh again.
    assert client.post("/api/v1/platforms/codewars/disconnect", headers=h).status_code == 200
    profile = UnifiedProfileService().get_unified_profile(user.id, db_session)
    skills = {s["slug"]: s for s in profile["skills"]}
    assert skills["recursion"]["status"] == "NO_EVIDENCE"
    assert profile["platform_counts"]["Codewars"] == 0


def test_resync_refreshes_stale_profile_stats_instead_of_ignoring_them(wired_connectors, db_session):
    """Regression: existing evidence rows were skipped, so profile stats never updated."""
    h = new_user_headers()
    first = client.post("/api/v1/platforms/codewars/sync", json={"username": "jhoffner"}, headers=h).json()
    assert first["synced_evidence_count"] == 4

    CW_STATE["total_completed"] = 7  # the user solved more kata upstream
    second = client.post("/api/v1/platforms/codewars/sync", json={"username": "jhoffner"}, headers=h).json()
    assert second["synced_evidence_count"] == 0
    assert second["updated_evidence_count"] == 4

    user = db_user(db_session, h)
    row = db_session.query(Evidence).filter_by(user_id=user.id, external_id="codewars_profile_jhoffner").one()
    db_session.refresh(row)
    assert row.normalized_payload["total_solved"] == 7
    assert "7 Kata" in row.title
    assert db_session.query(Evidence).filter_by(user_id=user.id).count() == 4  # no duplicates


def test_geeksforgeeks_full_sync(wired_connectors, db_session):
    h = new_user_headers()
    res = client.post("/api/v1/platforms/geeksforgeeks/sync", json={"username": "paji"}, headers=h)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["platform"] == "GeeksforGeeks"
    assert body["synced_evidence_count"] == 5  # profile + 4 problems
    assert body["profile_summary"]["total_solved"] == 335
    labels = {x["label"] for x in body["profile_summary"]["highlights"]}
    assert {"Coding score", "Institute rank", "Streak"} <= labels

    user = db_user(db_session, h)
    profile = UnifiedProfileService().get_unified_profile(user.id, db_session)
    assert profile["platform_counts"]["GeeksforGeeks"] == 5
    skills = {s["slug"]: s for s in profile["skills"]}
    assert skills["problem-solving"]["sources"]["GeeksforGeeks"] >= 1
    assert skills["python"]["sources"]["GeeksforGeeks"] >= 1


def test_codechef_full_sync_keeps_working_after_the_refactor(wired_connectors, db_session):
    h = new_user_headers()
    res = client.post("/api/v1/platforms/codechef/sync", json={"username": "demo_chef"}, headers=h)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["platform"] == "CodeChef"
    assert body["synced_evidence_count"] == 4  # profile + badge + 2 solved problems
    labels = {x["label"]: x["value"] for x in body["profile_summary"]["highlights"]}
    assert labels["Rating"] == 1850

    user = db_user(db_session, h)
    profile = UnifiedProfileService().get_unified_profile(user.id, db_session)
    assert profile["platform_counts"]["CodeChef"] == 4
    skills = {s["slug"]: s for s in profile["skills"]}
    assert skills["problem-solving"]["sources"]["CodeChef"] >= 1

    ghost = client.post("/api/v1/platforms/codechef/sync", json={"username": "ghost_chef"}, headers=h)
    assert ghost.status_code == 404


def test_all_new_platforms_together_and_case_only_rename(wired_connectors, db_session):
    h = new_user_headers()
    assert client.post("/api/v1/platforms/codewars/sync", json={"username": "jhoffner"}, headers=h).status_code == 200
    assert client.post("/api/v1/platforms/geeksforgeeks/sync", json={"username": "paji"}, headers=h).status_code == 200
    user = db_user(db_session, h)
    profile = UnifiedProfileService().get_unified_profile(user.id, db_session)
    assert profile["platform_counts"]["Codewars"] == 4
    assert profile["platform_counts"]["GeeksforGeeks"] == 5
    assert profile["total_evidence_count"] == 9

    # Case-only change = same account: nothing purged.
    assert client.post("/api/v1/platforms/codewars/sync", json={"username": "JHOFFNER"}, headers=h).status_code == 200
    conn = db_session.query(PlatformConnection).filter_by(user_id=user.id, platform="Codewars").one()
    db_session.refresh(conn)
    assert db_session.query(Evidence).filter_by(platform_connection_id=conn.id).count() == 4


def test_new_platform_evidence_excludes_solved_practice_problems(wired_connectors, db_session):
    """Your 'don't recommend what I already solved' logic works for Codewars/GfG slugs too."""
    from app.services.recommendations.problem_matcher import ProblemMatcherService

    h = new_user_headers()
    assert client.post("/api/v1/platforms/geeksforgeeks/sync", json={"username": "paji"}, headers=h).status_code == 200
    user = db_user(db_session, h)
    slugs = {
        (e.normalized_payload or {}).get("title_slug")
        for e in db_session.query(Evidence).filter_by(user_id=user.id, evidence_type="problem_submission")
    }
    assert "tic-tac-toe" in slugs  # exposed under the key your matcher reads
    recs = ProblemMatcherService().get_ranked_recommendations(user.id, "all", db_session, limit=50)
    assert recs  # still produces recommendations


# --------------------------------------------------------------------------- Clerk JWT auth


def _rsa_pair():
    pytest.importorskip("cryptography")  # installed via pyjwt[crypto]
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return pem, private.public_key()


@pytest.fixture()
def jwt_mode(monkeypatch):
    import types

    import app.api.v1.auth as auth
    from app.config import settings

    pem, public = _rsa_pair()
    fake_client = types.SimpleNamespace(
        get_signing_key_from_jwt=lambda token: types.SimpleNamespace(key=public)
    )
    monkeypatch.setattr(settings, "clerk_jwks_url", "https://example.test/.well-known/jwks.json")
    monkeypatch.setattr(settings, "clerk_issuer", "https://clerk.example.test")
    monkeypatch.setattr(auth, "_jwks_client", lambda url: fake_client)
    return pem


def _token(pem, **overrides):
    import time

    import jwt

    claims = {"sub": f"user_{uuid.uuid4().hex[:10]}", "iss": "https://clerk.example.test", "exp": int(time.time()) + 600}
    claims.update(overrides)
    return jwt.encode({k: v for k, v in claims.items() if v is not None}, pem, algorithm="RS256")


def test_jwt_mode_accepts_valid_token_and_ignores_forgeable_header(jwt_mode):
    ok = client.get("/api/v1/platforms", headers={"Authorization": f"Bearer {_token(jwt_mode)}"})
    assert ok.status_code == 200

    # The legacy 'I am user X' header is useless once JWT verification is configured.
    forged = client.get("/api/v1/platforms", headers={"X-Clerk-User-Id": "someone_else"})
    assert forged.status_code == 401


def test_jwt_mode_rejects_bad_tokens(jwt_mode):
    assert client.get("/api/v1/platforms", headers={"Authorization": f"Bearer {_token(jwt_mode, exp=1)}"}).status_code == 401
    assert client.get("/api/v1/platforms", headers={"Authorization": f"Bearer {_token(jwt_mode, iss='https://evil.test')}"}).status_code == 401
    assert client.get("/api/v1/platforms", headers={"Authorization": "Bearer not-a-jwt"}).status_code == 401
    assert client.get("/api/v1/platforms").status_code == 401


def test_jwt_user_maps_to_a_stable_account(jwt_mode, db_session):
    sub = f"user_{uuid.uuid4().hex[:10]}"
    token = _token(jwt_mode, sub=sub)
    for _ in range(2):
        assert client.get("/api/v1/platforms", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    assert db_session.query(User).filter_by(clerk_user_id=sub).count() == 1


def test_insecure_dev_auth_can_be_switched_off(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "clerk_jwks_url", None)
    monkeypatch.setattr(settings, "allow_insecure_dev_auth", False)
    assert client.get("/api/v1/platforms", headers=new_user_headers()).status_code == 401


def test_concurrent_first_login_race_returns_existing_user(db_session):
    """Two parallel first requests must not 500 on the unique clerk_user_id constraint."""
    from types import SimpleNamespace

    from app.api.v1 import auth
    from app.models import User

    clerk_id = "race_user_1"
    req = SimpleNamespace(headers={"x-clerk-user-id": clerk_id})
    real_extract = auth._extract_clerk_id
    auth._extract_clerk_id = lambda request: clerk_id
    try:
        first = auth.get_current_user(req, db_session)
        # Simulate the loser of the race: the lookup misses, the insert collides.
        original_query = db_session.query
        calls = {"n": 0}

        class _Miss:
            def filter(self, *a, **k):
                return self

            def first(self):
                calls["n"] += 1
                return None if calls["n"] == 1 else original_query(User).filter(User.clerk_user_id == clerk_id).first()

        db_session.query = lambda *a, **k: _Miss() if calls["n"] == 0 else original_query(*a, **k)
        second = auth.get_current_user(req, db_session)
        assert second.id == first.id
    finally:
        auth._extract_clerk_id = real_extract
        db_session.query = original_query
        db_session.query(User).filter(User.clerk_user_id == clerk_id).delete()
        db_session.commit()
