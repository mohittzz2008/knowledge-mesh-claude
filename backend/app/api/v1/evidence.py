"""API endpoints for querying normalized Evidence items."""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.user import User
from app.models.evidence import Evidence
from app.models.platform import PlatformConnection
from app.schemas.evidence import EvidenceItemSchema, EvidenceListResponse
from app.api.v1.auth import get_current_user

router = APIRouter(prefix="/evidence", tags=["Evidence"])


@router.get("", response_model=EvidenceListResponse)
def list_evidence(
    platform: Optional[str] = Query(None, description="Filter by platform (e.g. GitHub)"),
    evidence_type: Optional[str] = Query(None, description="Filter by type (e.g. repository, commit)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve normalized developer evidence items persisted in PostgreSQL for the authenticated user."""
    query = db.query(Evidence).filter(Evidence.user_id == current_user.id)

    if platform:
        query = query.join(PlatformConnection).filter(PlatformConnection.platform == platform)

    if evidence_type:
        query = query.filter(Evidence.evidence_type == evidence_type)

    total = query.count()
    items = query.order_by(Evidence.created_at.desc()).offset(offset).limit(limit).all()

    # Calculate evidence breakdown counts by platform for current user
    counts_query = (
        db.query(PlatformConnection.platform, func.count(Evidence.id))
        .join(Evidence, Evidence.platform_connection_id == PlatformConnection.id)
        .filter(Evidence.user_id == current_user.id)
        .group_by(PlatformConnection.platform)
        .all()
    )
    platform_counts = {p_name: count for p_name, count in counts_query}

    return EvidenceListResponse(
        items=[EvidenceItemSchema.model_validate(item) for item in items],
        total=total,
        platform_counts=platform_counts,
    )
