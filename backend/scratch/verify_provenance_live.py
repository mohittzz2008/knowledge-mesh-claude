"""Script to trace exact data lineage and provenance breakdown for current user."""

import uuid
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.user import User
from app.models.platform import PlatformConnection
from app.models.evidence import Evidence
from app.models.code_artifact import CodeArtifact
from app.services.mesh.unified_profile import UnifiedProfileService
from app.services.mesh.graph_builder import KnowledgeMeshGraphBuilder


def trace_provenance_lineage():
    sync_id = str(uuid.uuid4())[:8]
    print(f"==================================================================")
    print(f"      [SYNC {sync_id}] DATA LINEAGE & PROVENANCE TRACE")
    print(f"==================================================================")

    db: Session = SessionLocal()
    user = db.query(User).filter(User.clerk_user_id == "demo_clerk_user_id").first()
    if not user:
        print(f"[SYNC {sync_id}] User 'demo_clerk_user_id' not found in PostgreSQL!")
        db.close()
        return

    user_id = user.id
    print(f"[SYNC {sync_id}] Current Authenticated User ID: {user_id}")

    # 1. Connections
    connections = db.query(PlatformConnection).filter(PlatformConnection.user_id == user_id).all()
    print(f"\n[SYNC {sync_id}] PLATFORM CONNECTIONS:")
    for c in connections:
        print(f"   Platform: {c.platform:<12} | Connected: {str(c.connected):<5} | Username: {c.username}")

    # 2. Evidence Rows
    evidences = db.query(Evidence).filter(Evidence.user_id == user_id).all()
    print(f"\n[SYNC {sync_id}] POSTGRESQL EVIDENCE ROWS ({len(evidences)} total):")
    for e in evidences:
        plat = e.platform_connection.platform if e.platform_connection else "CodeLab"
        uname = e.platform_connection.username if e.platform_connection else "N/A"
        print(f"   ID: {e.id[:8]}... | Platform: {plat:<10} | Username: {uname:<15} | Type: {e.evidence_type:<20} | Title: {e.title}")

    # 3. Code Artifacts Rows
    artifacts = db.query(CodeArtifact).filter(CodeArtifact.user_id == user_id).all()
    print(f"\n[SYNC {sync_id}] POSTGRESQL CODE ARTIFACTS ({len(artifacts)} total):")
    art_by_platform = {}
    for a in artifacts:
        art_by_platform[a.platform] = art_by_platform.get(a.platform, 0) + 1
    for p, cnt in art_by_platform.items():
        print(f"   Platform: {p:<10} | Artifact Count: {cnt}")

    # 4. Unified Profile & Skill Sources Breakdown
    profile_service = UnifiedProfileService()
    profile = profile_service.get_unified_profile(user_id, db)

    print(f"\n[SYNC {sync_id}] UNIFIED DEVELOPER PROFILE SUMMARY:")
    print(f"   Overall Skill Score: {profile['overall_skill_score']}")
    print(f"   Total Evidence Count: {profile['total_evidence_count']}")
    print(f"   Code Artifacts Count: {profile['code_artifacts_count']}")
    print(f"   Platform Counts: {profile['platform_counts']}")

    print(f"\n[SYNC {sync_id}] EXACT SKILL MASTERY & SOURCE LINEAGE BREAKDOWN:")
    print("---------------------------------------------------------------------------------------------------------")
    print(f"{'SKILL NAME':<30} | {'MASTERY':<8} | {'EVIDENCE COUNT':<15} | {'SOURCES BREAKDOWN':<35}")
    print("---------------------------------------------------------------------------------------------------------")
    for s in profile["skills"]:
        srcs = s.get("sources", {})
        src_str = ", ".join([f"{k}: {v}" for k, v in srcs.items() if v > 0]) or "None"
        print(f"{s['skill_name']:<30} | {s['mastery']:<8} | {s['evidence_count']:<15} | {src_str:<35}")

    db.close()


if __name__ == "__main__":
    trace_provenance_lineage()
