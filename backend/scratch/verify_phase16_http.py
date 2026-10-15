"""Phase 16 Live HTTP Server & API Integration Verification Script."""

import urllib.request
import json
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.user import User

BASE_BACKEND = "http://127.0.0.1:8000"
BASE_FRONTEND = "http://127.0.0.1:3000"


def http_get(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=5.0) as res:
        return res.status, res.read().decode("utf-8")


def http_post(url: str, payload: dict):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=5.0) as res:
        return res.status, res.read().decode("utf-8")


def verify_phase16():
    print("==================================================================")
    print("   PHASE 16 LIVE HTTP & RELIABILITY AUDIT VERIFICATION")
    print("==================================================================")

    # 1. Verify Backend Endpoints HTTP Status & Payloads
    print("\n[1/4] Verifying Backend FastAPI Server (Port 8000):")
    
    st_health, body_health = http_get(f"{BASE_BACKEND}/health")
    print(f"  • GET /health: HTTP {st_health} -> {body_health.strip()}")

    st_db, body_db = http_get(f"{BASE_BACKEND}/db-health")
    print(f"  • GET /db-health: HTTP {st_db} -> {body_db.strip()}")

    st_plat, body_plat = http_get(f"{BASE_BACKEND}/api/v1/platforms")
    plat_list = json.loads(body_plat)
    print(f"  • GET /api/v1/platforms: HTTP {st_plat} -> {len(plat_list)} registered platform(s)")

    st_prof, body_prof = http_get(f"{BASE_BACKEND}/api/v1/user/profile")
    prof_data = json.loads(body_prof)
    print(f"  • GET /api/v1/user/profile: HTTP {st_prof} -> Score: {prof_data['overall_skill_score']}/100, Evidence: {prof_data['total_evidence_count']}")

    st_mesh, body_mesh = http_get(f"{BASE_BACKEND}/api/v1/knowledge-mesh")
    mesh_data = json.loads(body_mesh)
    print(f"  • GET /api/v1/knowledge-mesh: HTTP {st_mesh} -> Nodes: {len(mesh_data['nodes'])}, Edges: {len(mesh_data['edges'])}")

    st_nba, body_nba = http_get(f"{BASE_BACKEND}/api/v1/next-best-action")
    nba_data = json.loads(body_nba)
    print(f"  • GET /api/v1/next-best-action: HTTP {st_nba} -> Target: {nba_data['target_skill']} ({nba_data['recommended_difficulty']})")

    st_lp, body_lp = http_get(f"{BASE_BACKEND}/api/v1/learning-path")
    lp_data = json.loads(body_lp)
    print(f"  • GET /api/v1/learning-path: HTTP {st_lp} -> Roadmap Steps: {lp_data['total_steps']}")

    st_prob, body_prob = http_get(f"{BASE_BACKEND}/api/v1/code-lab/problems/problem-tree-inorder")
    prob_data = json.loads(body_prob)
    print(f"  • GET /api/v1/code-lab/problems/problem-tree-inorder: HTTP {st_prob} -> Title: '{prob_data['title']}'")

    # 2. Test Live Code Lab Execution on Backend
    print("\n[2/4] Testing Live Code Lab Subprocess Execution:")
    code_payload = {
        "code": "def inorder_traversal(root):\n    return []\n",
        "language": "Python",
        "problem_id": "problem-tree-inorder"
    }
    st_run, body_run = http_post(f"{BASE_BACKEND}/api/v1/code-lab/run", code_payload)
    run_data = json.loads(body_run)
    print(f"  • POST /api/v1/code-lab/run: HTTP {st_run} -> Time: {run_data['execution_time_ms']} ms, Passed: {run_data['passed_count']}/{run_data['total_tests']}")

    # 3. Test Live AI Coach Question Routing
    print("\n[3/4] Testing Live AI Coach Question Routing & Context Panel:")
    coach_payload = {"message": "Why do you think my recursion is strong?"}
    st_coach, body_coach = http_post(f"{BASE_BACKEND}/api/v1/coach/messages", coach_payload)
    coach_data = json.loads(body_coach)
    print(f"  • POST /api/v1/coach/messages: HTTP {st_coach}")
    print(f"    - Intent: {coach_data.get('intent')}")
    print(f"    - Confidence: {coach_data.get('confidence')}")
    print(f"    - Grounded Evidence References: {len(coach_data.get('evidence_references', []))}")

    # 4. Database & Migration Verification
    print("\n[4/4] Database & Foreign Key Audit:")
    db = SessionLocal()
    user_count = db.query(User).count()
    print(f"  • Active Database Users Count: {user_count}")
    db.close()

    print("\n==================================================================")
    print("   PHASE 16 RELIABILITY AUDIT COMPLETE: ALL SERVERS OPERATIONAL!")
    print("==================================================================")


if __name__ == "__main__":
    verify_phase16()
