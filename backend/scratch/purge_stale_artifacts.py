"""Script to inspect and purge stale CodeArtifacts & Evidence from PostgreSQL."""

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.platform import PlatformConnection
from app.models.evidence import Evidence
from app.models.code_artifact import CodeArtifact, CodeAnalysis
from app.models.user import User
from app.services.mesh.concept_extractor import ConceptExtractorService


def purge_stale_data():
    db: Session = SessionLocal()

    print("==================================================================")
    print("      BEFORE PURGE: DATA PROVENANCE DIAGNOSTIC")
    print("==================================================================")

    users = db.query(User).all()
    connections = db.query(PlatformConnection).all()
    evidences = db.query(Evidence).all()
    artifacts = db.query(CodeArtifact).all()

    print(f"Users Count: {len(users)}")
    print(f"Connections Count: {len(connections)}")
    for c in connections:
        print(f"  • Conn {c.id}: Platform={c.platform}, Username='{c.username}'")

    print(f"Total Evidence Count: {len(evidences)}")
    print(f"Total CodeArtifact Count: {len(artifacts)}")

    torvalds_arts = [a for a in artifacts if "torvalds" in a.repository.lower()]
    print(f"Stale 'torvalds' CodeArtifacts Count: {len(torvalds_arts)}")
    for a in torvalds_arts:
        print(f"  • Stale Artifact ID: {a.id} | Repo: {a.repository} | Path: {a.file_path}")

    # Perform Purge of stale 'torvalds' artifacts and evidence not matching current connection usernames
    print("\n==================================================================")
    print("      PURGING STALE 'torvalds' ARTIFACTS & EVIDENCE")
    print("==================================================================")

    # Delete torvalds CodeArtifacts
    for a in torvalds_arts:
        db.delete(a)

    # Delete stale Evidence with title or payload referencing torvalds
    torvalds_evs = db.query(Evidence).filter(Evidence.title.ilike("%torvalds%")).all()
    print(f"Stale 'torvalds' Evidence Count to delete: {len(torvalds_evs)}")
    for ev in torvalds_evs:
        db.delete(ev)

    db.commit()

    # Re-evaluate Knowledge Mesh assessments for all users
    extractor = ConceptExtractorService()
    for u in users:
        extractor.extract_and_assess_user_skills(u.id, db)

    print("\n==================================================================")
    print("      AFTER PURGE: VERIFIED DATA PROVENANCE")
    print("==================================================================")

    evidences_after = db.query(Evidence).all()
    artifacts_after = db.query(CodeArtifact).all()

    print(f"Total Evidence Count After Purge: {len(evidences_after)}")
    print(f"Total CodeArtifact Count After Purge: {len(artifacts_after)}")
    for a in artifacts_after:
        print(f"  • Artifact ID: {a.id} | Platform: {a.platform} | Repo: {a.repository} | Path: {a.file_path}")

    db.close()


if __name__ == "__main__":
    purge_stale_data()
