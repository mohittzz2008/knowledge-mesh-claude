"""Unit tests for GitHub Connector & Normalization Engine."""

import pytest
from app.services.platform.github import GitHubConnector

@pytest.mark.live
@pytest.mark.asyncio
async def test_github_connector_validation():
    connector = GitHubConnector()

    # Test empty username returns False
    is_empty_valid = await connector.validate_identity("")
    assert is_empty_valid is False

    # Test valid public username (torvalds)
    is_torvalds_valid = await connector.validate_identity("torvalds")
    assert is_torvalds_valid is True

    # Test invalid username
    is_invalid = await connector.validate_identity("this_user_definitely_does_not_exist_998877112233")
    assert is_invalid is False


@pytest.mark.live
@pytest.mark.asyncio
async def test_github_profile_fetch():
    connector = GitHubConnector()
    profile = await connector.fetch_profile("torvalds")
    assert profile is not None
    assert profile["username"].lower() == "torvalds"
    assert profile["public_repos"] > 0


def test_github_evidence_normalization():
    connector = GitHubConnector()

    raw_repo_item = {
        "type": "repository",
        "data": {
            "id": 12345,
            "name": "knowledge-mesh",
            "full_name": "developer/knowledge-mesh",
            "language": "Python",
            "topics": ["ai", "fastapi", "nextjs"],
            "stargazers_count": 42,
            "html_url": "https://github.com/developer/knowledge-mesh",
            "updated_at": "2026-08-22T16:00:00Z",
            "description": "Developer intelligence system",
        },
    }

    normalized = connector.normalize_evidence(raw_repo_item)

    assert normalized["platform"] == "GitHub"
    assert normalized["external_id"] == "github_repo_12345"
    assert normalized["evidence_type"] == "repository"
    assert "Repository: developer/knowledge-mesh" in normalized["title"]
    assert "Python" in normalized["normalized_payload"]["skills"]
    assert "Ai" in normalized["normalized_payload"]["skills"] or "ai" in [s.lower() for s in normalized["normalized_payload"]["skills"]]
    assert normalized["normalized_payload"]["stars"] == 42


def test_github_activity_normalization():
    connector = GitHubConnector()

    raw_activity_item = {
        "type": "activity",
        "data": {
            "id": "999888",
            "type": "PushEvent",
            "repo": {"name": "owner/repo"},
            "created_at": "2026-08-22T16:30:00Z",
            "payload": {
                "commits": [{"sha": "abc1234", "message": "feat: add github connector"}],
            },
        },
    }

    normalized = connector.normalize_evidence(raw_activity_item)

    assert normalized["platform"] == "GitHub"
    assert normalized["external_id"] == "github_event_999888"
    assert normalized["evidence_type"] == "commit"
    assert "Pushed 1 commit(s) to owner/repo" in normalized["title"]
    assert "Git" in normalized["normalized_payload"]["skills"]
