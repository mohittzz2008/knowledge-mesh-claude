"""SQL Provenance Audit Script executing exact Part 21 database queries."""

from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.user import User


def run_sql_provenance_audit():
    db: Session = SessionLocal()

    user = db.query(User).filter(User.clerk_user_id == "demo_clerk_user_id").first()
    if not user:
        print("No user found for clerk_user_id = 'demo_clerk_user_id'")
        db.close()
        return

    user_id = user.id

    print("==================================================================")
    print(f"      POSTGRESQL EVIDENCE PROVENANCE AUDIT (User ID: {user_id})")
    print("==================================================================")

    # 1. Evidence Query
    sql_ev = text("""
        SELECT pc.platform, pc.username AS platform_username, COUNT(e.id) AS evidence_count
        FROM evidence e
        LEFT JOIN platform_connections pc ON e.platform_connection_id = pc.id
        WHERE e.user_id = :user_id
        GROUP BY pc.platform, pc.username;
    """)

    res_ev = db.execute(sql_ev, {"user_id": user_id}).fetchall()

    print("\nEVIDENCE BY PLATFORM & USERNAME:")
    print("------------------------------------------------------------------")
    print(f"{'PLATFORM':<15} | {'PLATFORM USERNAME':<25} | {'EVIDENCE COUNT':<15}")
    print("------------------------------------------------------------------")
    for r in res_ev:
        plat = r.platform or "CodeLab"
        uname = r.platform_username or "N/A (CodeLab Internal)"
        print(f"{plat:<15} | {uname:<25} | {r.evidence_count:<15}")

    # 2. Code Artifacts Query
    sql_art = text("""
        SELECT ca.platform, pc.username AS platform_username, COUNT(ca.id) AS artifact_count
        FROM code_artifacts ca
        LEFT JOIN platform_connections pc ON ca.platform_connection_id = pc.id
        WHERE ca.user_id = :user_id
        GROUP BY ca.platform, pc.username;
    """)

    res_art = db.execute(sql_art, {"user_id": user_id}).fetchall()

    print("\nCODE ARTIFACTS BY PLATFORM & USERNAME:")
    print("------------------------------------------------------------------")
    print(f"{'PLATFORM':<15} | {'PLATFORM USERNAME':<25} | {'ARTIFACT COUNT':<15}")
    print("------------------------------------------------------------------")
    for r in res_art:
        plat = r.platform or "CodeLab"
        uname = r.platform_username or "N/A (CodeLab Internal)"
        print(f"{plat:<15} | {uname:<25} | {r.artifact_count:<15}")

    db.close()


if __name__ == "__main__":
    run_sql_provenance_audit()
