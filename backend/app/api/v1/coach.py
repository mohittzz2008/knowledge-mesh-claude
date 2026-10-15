"""FastAPI Router for Contextual AI Coding Coach APIs."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.api.v1.auth import get_current_user
from app.schemas.coach import (
    CoachMessageCreate,
    CoachMessageResponse,
    CoachConversationSchema,
    CoachConversationDetailResponse,
    AnalyzeLogicRequest,
    AnalyzeLogicResponse,
    CompareApproachRequest,
    CompareApproachResponse,
)
from app.services.coach.coach_service import CoachService
from app.services.coach.provider_base import CoachProviderError, CoachUnavailableError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/coach", tags=["AI Coding Coach"])


@router.post("/messages", response_model=CoachMessageResponse)
def post_coach_message(
    payload: CoachMessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send user message to AI Coach, grounded in PostgreSQL evidence and Knowledge Mesh."""
    service = CoachService()
    try:
        res = service.process_user_message(
            user_id=current_user.id,
            message=payload.message,
            db=db,
            conversation_id=payload.conversation_id,
            code_artifact_id=payload.code_artifact_id,
        )
    except CoachUnavailableError as err:
        logger.warning("Coach unavailable: %s", err)
        raise HTTPException(status_code=503, detail="The AI coach is not configured on this server.") from err
    except CoachProviderError as err:
        raise HTTPException(status_code=502, detail="The AI provider failed. Please try again.") from err
    return CoachMessageResponse.model_validate(res)


@router.get("/conversations", response_model=list[CoachConversationSchema])
def list_coach_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List active coaching conversations for current user."""
    service = CoachService()
    convs = service.get_user_conversations(current_user.id, db)
    return [CoachConversationSchema.model_validate(c) for c in convs]


@router.get("/conversations/{conversation_id}", response_model=CoachConversationDetailResponse)
def get_coach_conversation_detail(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve full message history for a specific coaching conversation."""
    service = CoachService()
    detail = service.get_conversation_history(conversation_id, current_user.id, db)
    return CoachConversationDetailResponse.model_validate(detail)


@router.post("/analyze-logic", response_model=AnalyzeLogicResponse)
def analyze_logic(
    payload: AnalyzeLogicRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Analyze entire submitted source code logic and return structured AST insights."""
    service = CoachService()
    res = service.analyze_logic(user_id=current_user.id, request=payload, db=db)
    return AnalyzeLogicResponse.model_validate(res)


@router.post("/compare-approach", response_model=CompareApproachResponse)
def compare_approach(
    payload: CompareApproachRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Compare two coding approaches for correctness, complexity, and maintainability."""
    service = CoachService()
    res = service.compare_approach(user_id=current_user.id, request=payload, db=db)
    return CompareApproachResponse.model_validate(res)
