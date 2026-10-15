"""Automated Regression Test for Platform Connection Username Switching & Data Provenance Purge."""

import uuid
from unittest.mock import AsyncMock, patch
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models.user import User
from app.models.platform import PlatformConnection
from app.models.evidence import Evidence
from app.models.code_artifact import CodeArtifact
from app.services.platform.github import GitHubConnector


def test_platform_username_switch_provenance_purge():
    """Verify that switching a platform connection username purges stale Evidence and CodeArtifacts of previous username while leaving Code Lab data intact."""
    db: Session = SessionLocal()
    client = TestClient(app)

    test_clerk_id = f"clerk_switch_{uuid.uuid4().hex[:6]}"
    headers = {"X-Clerk-User-Id": test_clerk_id}

    # 1. Connect GitHub as User A ('torvalds')
    mock_torvalds_profile = {
        "platform": "GitHub",
        "username": "torvalds",
        "name": "Linus Torvalds",
        "public_repos": 12,
        "followers": 200000,
        "avatar_url": "https://github.com/torvalds.png",
    }
    mock_torvalds_evidence = [
        {
            "type": "repository",
            "data": {
                "id": 1001,
                "name": "linux",
                "full_name": "torvalds/linux",
                "language": "C",
                "updated_at": "2026-08-22T10:00:00Z",
            },
        }
    ]
    mock_torvalds_file = {
        "path": "app/tree.py",
        "sha": "sha_torvalds_123",
        "size": 180,
        "html_url": "https://github.com/torvalds/linux/blob/master/app/tree.py",
        "code_content": "def recursion_tree(node):\n    if not node: return\n    recursion_tree(node.left)\n",
    }

    with patch.object(GitHubConnector, 'validate_identity', new=AsyncMock(return_value=True)), \
         patch.object(GitHubConnector, 'fetch_profile', new=AsyncMock(return_value=mock_torvalds_profile)), \
         patch.object(GitHubConnector, 'fetch_evidence', new=AsyncMock(return_value=mock_torvalds_evidence)), \
         patch.object(GitHubConnector, 'fetch_file_content', new=AsyncMock(return_value=mock_torvalds_file)):

        # Sync User A ('torvalds')
        res_sync_a = client.post("/api/v1/platforms/github/sync", json={"username": "torvalds"}, headers=headers)
        assert res_sync_a.status_code == 200

        # Analyze User A Code File ('torvalds/linux')
        res_art_a = client.post(
            "/api/v1/code-artifacts/analyze-github-file",
            json={"owner": "torvalds", "repo": "linux", "path": "app/tree.py"},
            headers=headers,
        )
        assert res_art_a.status_code == 200

        # Create 1 Code Lab attempt artifact for user
        user = db.query(User).filter(User.clerk_user_id == test_clerk_id).first()
        conn = db.query(PlatformConnection).filter(PlatformConnection.user_id == user.id, PlatformConnection.platform == "GitHub").first()
        
        codelab_art = CodeArtifact(
            user_id=user.id,
            platform_connection_id=conn.id,
            platform="CodeLab",
            repository="knowledge-mesh/code-lab",
            file_path="code-lab/tree-traversal.py",
            language="Python",
            code_content="def inorder(root): pass",
        )
        db.add(codelab_art)
        db.commit()

        # Verify User A data exists
        ev_count_a = db.query(Evidence).filter(Evidence.user_id == user.id, Evidence.platform_connection_id == conn.id).count()
        art_count_a = db.query(CodeArtifact).filter(CodeArtifact.user_id == user.id, CodeArtifact.platform_connection_id == conn.id).count()
        assert ev_count_a >= 1
        assert art_count_a == 2  # 1 torvalds file + 1 CodeLab file

    # 2. Switch connection to User B ('amruthnag20')
    mock_b_profile = {
        "platform": "GitHub",
        "username": "amruthnag20",
        "name": "Amruth Nag",
        "public_repos": 1,
        "followers": 5,
        "avatar_url": "https://github.com/amruthnag20.png",
    }
    mock_b_evidence = [
        {
            "type": "repository",
            "data": {
                "id": 2002,
                "name": "synapse",
                "full_name": "amruthnag20/synapse",
                "language": "Python",
                "updated_at": "2026-08-22T12:00:00Z",
            },
        }
    ]

    with patch.object(GitHubConnector, 'validate_identity', new=AsyncMock(return_value=True)), \
         patch.object(GitHubConnector, 'fetch_profile', new=AsyncMock(return_value=mock_b_profile)), \
         patch.object(GitHubConnector, 'fetch_evidence', new=AsyncMock(return_value=mock_b_evidence)):

        # Sync User B ('amruthnag20') on SAME connection
        res_sync_b = client.post("/api/v1/platforms/github/sync", json={"username": "amruthnag20"}, headers=headers)
        assert res_sync_b.status_code == 200

        # 3. Assertions after Username Switch:
        # a. Torvalds evidence must be 0
        torvalds_ev_count = db.query(Evidence).filter(Evidence.user_id == user.id, Evidence.title.ilike("%torvalds%")).count()
        assert torvalds_ev_count == 0, "PROVENANCE FAILURE: Stale 'torvalds' evidence lingered!"

        # b. Torvalds artifacts must be 0
        torvalds_art_count = db.query(CodeArtifact).filter(CodeArtifact.user_id == user.id, CodeArtifact.repository.ilike("%torvalds%")).count()
        assert torvalds_art_count == 0, "PROVENANCE FAILURE: Stale 'torvalds' CodeArtifact lingered!"

        # c. User B's real evidence present
        b_ev_count = db.query(Evidence).filter(Evidence.user_id == user.id, Evidence.title.ilike("%synapse%")).count()
        assert b_ev_count >= 1, "User B evidence not persisted!"

        # d. Code Lab artifact remains intact
        codelab_count = db.query(CodeArtifact).filter(CodeArtifact.user_id == user.id, CodeArtifact.platform == "CodeLab").count()
        assert codelab_count == 1, "Code Lab seed artifact was accidentally deleted!"

        # e. Skill detail endpoint returns 0 torvalds artifacts
        res_skill = client.get("/api/v1/knowledge-mesh/skills/recursion", headers=headers)
        assert res_skill.status_code == 200
        artifacts_returned = res_skill.json()["artifacts"]
        torvalds_in_mesh = [a for a in artifacts_returned if "torvalds" in a["repository"]]
        assert len(torvalds_in_mesh) == 0, "Knowledge Mesh still references torvalds artifact!"

    # Clean up test user
    db.delete(user)
    db.commit()
    db.close()
    print("--> [PASS] Username Switching Data Provenance Purge Test PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    test_platform_username_switch_provenance_purge()
