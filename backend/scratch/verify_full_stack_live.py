"""Full-Stack Real Data Integration Verification Script."""

from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models.user import User
from app.models.platform import PlatformConnection
from app.models.evidence import Evidence
from app.models.code_artifact import CodeArtifact

def run_full_stack_live_verification():
    db: Session = SessionLocal()
    client = TestClient(app)
    headers = {"X-Clerk-User-Id": "demo_clerk_user_id"}

    print("==================================================================")
    print("      KNOWLEDGE MESH LIVE FULL-STACK INTEGRATION AUDIT")
    print("==================================================================")

    # 1. Sync GitHub username 'amruthnag20'
    print("\n[1/7] Syncing Real GitHub Identity: 'amruthnag20'...")
    res_gh = client.post("/api/v1/platforms/github/sync", json={"username": "amruthnag20"}, headers=headers)
    assert res_gh.status_code == 200, f"GitHub Sync Failed: {res_gh.text}"
    gh_data = res_gh.json()
    print(f"  • Status: {gh_data['message']}")
    print(f"  • Synced Count: {gh_data['synced_evidence_count']}")
    print(f"  • Profile Summary: {gh_data['profile_summary']}")

    # 2. Sync LeetCode username 'H29bfENjLC'
    print("\n[2/7] Syncing Real LeetCode Identity: 'H29bfENjLC'...")
    res_lc = client.post("/api/v1/platforms/leetcode/sync", json={"username": "H29bfENjLC"}, headers=headers)
    assert res_lc.status_code == 200, f"LeetCode Sync Failed: {res_lc.text}"
    lc_data = res_lc.json()
    print(f"  • Status: {lc_data['message']}")
    print(f"  • Synced Count: {lc_data['synced_evidence_count']}")
    print(f"  • Profile Summary: {lc_data['profile_summary']}")

    # 3. Query PostgreSQL Evidence Records
    user = db.query(User).filter(User.clerk_user_id == "demo_clerk_user_id").first()
    evidences = db.query(Evidence).filter(Evidence.user_id == user.id).all()
    artifacts = db.query(CodeArtifact).filter(CodeArtifact.user_id == user.id).all()

    print(f"\n[3/7] PostgreSQL Persisted Evidence Summary for User '{user.id}':")
    print(f"  • Total Persisted Evidence: {len(evidences)}")
    print(f"  • Total CodeArtifacts: {len(artifacts)}")
    for ev in evidences:
        print(f"    - [{ev.platform_connection.platform if ev.platform_connection else 'Unknown'}] {ev.title} (ID: {ev.external_id})")

    # 4. Fetch User Profile & Dashboard Endpoint
    print("\n[4/7] Verifying /api/v1/user/profile (Dashboard API)...")
    res_prof = client.get("/api/v1/user/profile", headers=headers)
    assert res_prof.status_code == 200
    prof_data = res_prof.json()
    print(f"  • Overall Skill Score: {prof_data['overall_skill_score']}")
    print(f"  • Total Evidence Count: {prof_data['total_evidence_count']}")
    print(f"  • Platform Counts: {prof_data['platform_counts']}")
    print(f"  • Connected Platforms: {prof_data['connected_platforms']}")

    # Reconcile counts
    assert prof_data['total_evidence_count'] == len(evidences), "DASHBOARD MISMATCH: Total evidence count does not match PostgreSQL!"

    # 5. Fetch Knowledge Mesh Graph
    print("\n[5/7] Verifying /api/v1/knowledge-mesh Graph...")
    res_mesh = client.get("/api/v1/knowledge-mesh", headers=headers)
    assert res_mesh.status_code == 200
    mesh_data = res_mesh.json()
    print(f"  • Total Skills: {mesh_data['total_skills']}")
    print(f"  • Assessed Skills: {mesh_data['assessed_skills_count']}")

    # 6. Fetch Learning Path
    print("\n[6/7] Verifying /api/v1/learning-path Roadmap...")
    res_lp = client.get("/api/v1/learning-path", headers=headers)
    assert res_lp.status_code == 200
    lp_data = res_lp.json()
    print(f"  • Target Goal: {lp_data['target_goal']}")
    print(f"  • Current Focus Skill: {lp_data['current_focus_skill']}")
    print(f"  • Steps Count: {lp_data['total_steps']}")

    # 7. Query AI Coach Context Grounding
    print("\n[7/7] Verifying /api/v1/coach/messages Grounded Answer...")
    res_coach = client.post("/api/v1/coach/messages", json={"message": "What verified evidence do you have about my coding background?"}, headers=headers)
    assert res_coach.status_code == 200
    coach_data = res_coach.json()
    print(f"  • AI Coach Grounded Answer Snippet: {coach_data['answer'][:180]}...")
    print(f"  • Evidence References Used: {len(coach_data['evidence_references'])}")
    for ref in coach_data['evidence_references']:
        print(f"    - Ref: [{ref['platform']}] {ref['title']}")

    db.close()
    print("\n==================================================================")
    print("      LIVE FULL-STACK RECONCILIATION VERIFICATION COMPLETED!")
    print("==================================================================")


if __name__ == "__main__":
    run_full_stack_live_verification()
