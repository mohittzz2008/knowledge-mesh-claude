"""FastAPI Router for Code Lab Execution, Diagnostics, and Submissions."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.api.v1.auth import get_current_user
from app.schemas.code_lab import (
    CodeRunRequest,
    CodeRunResponse,
    CodeAnalyzeRequest,
    CodeAnalyzeResponse,
    CodeSubmitRequest,
    CodeSubmitResponse,
    CodeHintRequest,
    CodeHintResponse,
)
from app.services.code_lab.code_lab_service import CodeLabService

router = APIRouter(prefix="/code-lab", tags=["Code Lab"])


@router.get("/problems/{problem_id}")
def get_code_lab_problem(problem_id: str):
    """Retrieve normalized Code Lab problem details and test cases."""
    service = CodeLabService()
    p = service.get_problem_detail(problem_id)
    if not p:
        raise HTTPException(status_code=404, detail="Problem not found")
    return p


@router.post("/run", response_model=CodeRunResponse)
def run_code_lab_test_cases(payload: CodeRunRequest):
    """Run user code safely in isolated subprocess against test cases (no unsafe exec/eval in API process)."""
    service = CodeLabService()
    res = service.run_code(payload.code, payload.language, payload.problem_id)
    return CodeRunResponse.model_validate(res)


@router.post("/analyze", response_model=CodeAnalyzeResponse)
def analyze_code_lab_logic(payload: CodeAnalyzeRequest):
    """Perform AST static analysis, AI reasoning diagnostics, and AI suggested code diff generation."""
    service = CodeLabService()
    res = service.analyze_code(payload.code, payload.language, payload.problem_id)
    return CodeAnalyzeResponse.model_validate(res)


@router.post("/submit", response_model=CodeSubmitResponse)
def submit_code_lab_solution(
    payload: CodeSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Execute submission, record CodeAttempt & Evidence, and refresh PostgreSQL Knowledge Mesh telemetry."""
    service = CodeLabService()
    res = service.submit_code(
        user_id=current_user.id,
        problem_id=payload.problem_id,
        code=payload.code,
        language=payload.language,
        db=db,
    )
    return CodeSubmitResponse.model_validate(res)


@router.post("/hint", response_model=CodeHintResponse)
def get_code_lab_hint(payload: CodeHintRequest):
    """Get progressive hints for a problem."""
    service = CodeLabService()
    res = service.get_hint(payload.problem_id, payload.hint_level)
    return CodeHintResponse.model_validate(res)
