"""FastAPI Router for Unified Developer Profile & Cross-Platform Telemetry."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.api.v1.auth import get_current_user
from app.schemas.user import UserProfileResponse
from app.services.mesh.unified_profile import UnifiedProfileService
from app.models.evidence import Evidence

router = APIRouter(prefix="/user", tags=["User Profile"])


@router.get("/profile", response_model=UserProfileResponse)
def get_unified_user_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve aggregated cross-platform developer profile with deduplicated telemetry."""
    service = UnifiedProfileService()
    profile = service.get_unified_profile(current_user.id, db)
    return UserProfileResponse.model_validate(profile)


@router.get("/provenance")
def get_user_provenance_debug(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve detailed provenance breakdown for current authenticated user."""
    service = UnifiedProfileService()
    profile = service.get_unified_profile(current_user.id, db)
    evidence_items = db.query(Evidence).filter(Evidence.user_id == current_user.id).all()
    ev_ids = [e.id for e in evidence_items]

    return {
        "user_id": current_user.id,
        "clerk_user_id": current_user.clerk_user_id,
        "email": current_user.email,
        "dashboard": {
            "overall_skill_score": profile["overall_skill_score"],
            "total_evidence_count": profile["total_evidence_count"]
        },
        "platform_counts": profile["platform_counts"],
        "connected_platforms": profile["connected_platforms"],
        "skills_provenance": [
            {
                "skill": s["skill_name"],
                "score": s["mastery"],
                "status": s["status"],
                "evidence_count": s["evidence_count"],
                "sources": s["sources"],
            }
            for s in profile["skills"]
        ],
        "score_provenance": {
            "source": "PostgreSQL Evidence",
            "user_id": current_user.id,
            "evidence_count": len(ev_ids),
            "evidence_ids": ev_ids
        }
    }
