"""Data Integrity Verification & PostgreSQL Evidence Traceability Audit."""

import asyncio
import json
from typing import Any
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.user import User, DeveloperProfile
from app.models.platform import PlatformConnection
from app.models.evidence import Evidence
from app.models.code_artifact import CodeArtifact, CodeAnalysis
from app.services.platform.github import GitHubConnector
from app.services.platform.leetcode import LeetCodeConnector


async def test_amruthnag20_github_api():
    """Verify live GitHub API response for 'amruthnag20'."""
    connector = GitHubConnector()
    is_valid = await connector.validate_identity("amruthnag20")
    profile = await connector.fetch_profile("amruthnag20")
    evidence = await connector.fetch_evidence("amruthnag20")
    return {
        "valid": is_valid,
        "profile": profile,
        "raw_evidence_count": len(evidence),
        "evidence_sample": evidence[:2] if evidence else [],
    }


def audit_postgresql_integrity():
    db: Session = SessionLocal()

    print("==================================================================")
    print("      POSTGRESQL DATA INTEGRITY & EVIDENCE AUDIT")
    print("==================================================================")

    # 1. Users and Profiles
    users = db.query(User).all()
    print(f"\n[1/5] Database Users Count: {len(users)}")
    for u in users:
        print(f"  • User ID: {u.id} | Clerk ID: {u.clerk_user_id} | Email: {u.email} | Name: {u.full_name}")

    # 2. Platform Connections
    connections = db.query(PlatformConnection).all()
    print(f"\n[2/5] Platform Connections Count: {len(connections)}")
    for c in connections:
        print(f"  • Conn ID: {c.id} | User ID: {c.user_id} | Platform: {c.platform} | Username: '{c.username}' | Connected: {c.connected} | Last Synced: {c.last_synced_at}")

    # 3. Evidence Breakdown by Connection and Platform
    evidences = db.query(Evidence).all()
    print(f"\n[3/5] Total Evidence Records in PostgreSQL: {len(evidences)}")

    conn_breakdown = {}
    for ev in evidences:
        conn = db.query(PlatformConnection).filter(PlatformConnection.id == ev.platform_connection_id).first()
        conn_uname = conn.username if conn else "ORPHAN"
        conn_plat = conn.platform if conn else "UNKNOWN"

        key = (ev.user_id, conn_plat, conn_uname)
        conn_breakdown[key] = conn_breakdown.get(key, 0) + 1

    print("\n  Evidence Breakdown by (User ID, Platform, Connected Username):")
    for (u_id, plat, uname), count in conn_breakdown.items():
        print(f"  • User '{u_id}' -> Platform: {plat}, Username: '{uname}' => {count} Evidence Record(s)")

    # 4. Specific Question Counts
    count_torvalds = db.query(Evidence).join(PlatformConnection).filter(PlatformConnection.username == "torvalds").count()
    count_amruthnag20 = db.query(Evidence).join(PlatformConnection).filter(PlatformConnection.username == "amruthnag20").count()
    count_demo_lc = db.query(Evidence).join(PlatformConnection).filter(PlatformConnection.username == "demo_lc_user_test").count()

    print("\n[4/5] Username Specific Evidence Counts:")
    print(f"  • Evidence from 'torvalds': {count_torvalds}")
    print(f"  • Evidence from 'amruthnag20': {count_amruthnag20}")
    print(f"  • Evidence from 'demo_lc_user_test': {count_demo_lc}")

    # 5. Code Artifacts Breakdown
    artifacts = db.query(CodeArtifact).all()
    print(f"\n[5/5] Total CodeArtifacts in PostgreSQL: {len(artifacts)}")
    for a in artifacts:
        print(f"  • Artifact ID: {a.id} | User ID: {a.user_id} | Repo: {a.repository} | Path: {a.file_path}")

    db.close()
    return {
        "count_torvalds": count_torvalds,
        "count_amruthnag20": count_amruthnag20,
        "count_demo_lc": count_demo_lc,
        "total_evidence": len(evidences),
    }


def main():
    res_db = audit_postgresql_integrity()

    print("\n==================================================================")
    print("      LIVE GITHUB API AUDIT FOR 'amruthnag20'")
    print("==================================================================")
    api_res = asyncio.run(test_amruthnag20_github_api())
    print(f"  • Is Valid GitHub Identity: {api_res['valid']}")
    print(f"  • Profile Summary: {api_res['profile']}")
    print(f"  • Raw Evidence Items Returned by API: {api_res['raw_evidence_count']}")
    if api_res['raw_evidence_count'] > 0:
        print(f"  • Sample Item 1: {api_res['evidence_sample'][0]['type']} - {api_res['evidence_sample'][0]['data'].get('name') or api_res['evidence_sample'][0]['data'].get('full_name')}")

    print("\n==================================================================")
    print("      AUDIT EXECUTION COMPLETE")
    print("==================================================================")


if __name__ == "__main__":
    main()
