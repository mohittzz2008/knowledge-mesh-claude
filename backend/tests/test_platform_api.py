"""Integration tests for GitHub Platform API Endpoints."""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check_endpoints():
    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "ok"

    res_db = client.get("/db-health")
    assert res_db.status_code == 200
    assert res_db.json()["database"] == "connected"


@pytest.mark.live
def test_github_validate_valid_user():
    res = client.post(
        "/api/v1/platforms/github/validate",
        json={"username": "torvalds"},
        headers={"X-Clerk-User-Id": "demo_clerk_user_id"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["platform"] == "GitHub"
    assert data["valid"] is True
    assert data["public_repos"] > 0


@pytest.mark.live
def test_github_validate_invalid_user():
    res = client.post(
        "/api/v1/platforms/github/validate",
        json={"username": "this_user_definitely_does_not_exist_998877112233"},
        headers={"X-Clerk-User-Id": "demo_clerk_user_id"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["platform"] == "GitHub"
    assert data["valid"] is False


@pytest.mark.live
def test_github_sync_flow():
    # Sync public repositories & events for valid username
    res = client.post(
        "/api/v1/platforms/github/sync",
        json={"username": "torvalds", "auth_type": "username_public"},
        headers={"X-Clerk-User-Id": "demo_clerk_user_id"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["platform"] == "GitHub"
    assert data["connected"] is True
    assert data["synced_evidence_count"] >= 0

    # Query persisted evidence via API
    res_evidence = client.get(
        "/api/v1/evidence?platform=GitHub",
        headers={"X-Clerk-User-Id": "demo_clerk_user_id"}
    )
    assert res_evidence.status_code == 200
    evidence_data = res_evidence.json()
    assert "items" in evidence_data
    assert "GitHub" in evidence_data.get("platform_counts", {})
