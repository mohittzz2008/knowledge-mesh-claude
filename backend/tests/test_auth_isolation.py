"""Automated Test Suite for Clerk User Mapping & Strict Multi-Tenant Isolation."""

import uuid
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models.user import User, DeveloperProfile
from app.models.platform import PlatformConnection
from app.models.evidence import Evidence
from app.models.code_artifact import CodeArtifact
from app.api.v1.auth import get_current_user


def test_clerk_user_mapping_and_isolation():
    """Verify Clerk user mapping, idempotency, and strict user isolation."""
    db: Session = SessionLocal()

    clerk_id_a = f"user_clerk_{uuid.uuid4().hex[:6]}"
    clerk_id_b = f"user_clerk_{uuid.uuid4().hex[:6]}"

    client = TestClient(app)

    # 1. First-time login for User A via API header
    res_a = client.get("/api/v1/user/profile", headers={"X-Clerk-User-Id": clerk_id_a})
    assert res_a.status_code == 200
    data_a = res_a.json()
    assert data_a["developer_name"] == "Knowledge Mesh Developer"

    # 2. Verify User A row created in PostgreSQL
    user_a = db.query(User).filter(User.clerk_user_id == clerk_id_a).first()
    assert user_a is not None

    # 3. Repeat login for User A (Idempotency check)
    res_a_again = client.get("/api/v1/user/profile", headers={"X-Clerk-User-Id": clerk_id_a})
    assert res_a_again.status_code == 200
    user_a_count = db.query(User).filter(User.clerk_user_id == clerk_id_a).count()
    assert user_a_count == 1, "IDEMPOTENCY FAILURE: Duplicate User row created!"

    # 4. Create platform connection & evidence for User A only
    conn_a = PlatformConnection(user_id=user_a.id, platform="GitHub", connected=True, username="user_a_dev")
    db.add(conn_a)
    db.commit()

    ev_a = Evidence(
        user_id=user_a.id,
        platform_connection_id=conn_a.id,
        title="User A Private Evidence",
        evidence_type="repository",
        external_id=f"ev_a_{uuid.uuid4().hex[:6]}",
        normalized_payload={"skills": ["Recursion"]}
    )
    db.add(ev_a)
    db.commit()

    # 5. User B logs in
    res_b = client.get("/api/v1/user/profile", headers={"X-Clerk-User-Id": clerk_id_b})
    assert res_b.status_code == 200
    data_b = res_b.json()
    assert data_b["total_evidence_count"] == 0, "ISOLATION FAILURE: User B saw User A evidence!"

    # 6. User B queries evidence endpoint
    res_ev_b = client.get("/api/v1/evidence", headers={"X-Clerk-User-Id": clerk_id_b})
    assert res_ev_b.status_code == 200
    ev_list_b = res_ev_b.json()
    assert ev_list_b["total"] == 0, "ISOLATION FAILURE: User B queried User A evidence list!"

    # 7. User A queries evidence endpoint -> must see 1 item
    res_ev_a = client.get("/api/v1/evidence", headers={"X-Clerk-User-Id": clerk_id_a})
    assert res_ev_a.status_code == 200
    ev_list_a = res_ev_a.json()
    assert ev_list_a["total"] == 1, "User A failed to see own evidence!"

    # Clean up test rows
    db.delete(ev_a)
    db.delete(conn_a)
    db.delete(user_a)
    user_b = db.query(User).filter(User.clerk_user_id == clerk_id_b).first()
    if user_b:
        db.delete(user_b)
    db.commit()
    db.close()
    print("--> [PASS] User Mapping, Idempotency, and Multi-Tenant User Isolation Tests PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    test_clerk_user_mapping_and_isolation()
