"""API endpoints for CodeArtifacts, Source Code Retrieval & AST Code Intelligence."""

from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.platform import PlatformConnection
from app.models.code_artifact import CodeArtifact, CodeAnalysis
from app.models.evidence import Evidence
from app.api.v1.auth import get_current_user
from app.schemas.code_artifact import (
    CodeArtifactSchema,
    CodeAnalysisSchema,
    CodeArtifactListResponse,
    AnalyzeGitHubFileRequest,
)
from app.services.platform.github import GitHubConnector
from app.services.analysis.code_analyzer import CodeAnalyzerService

router = APIRouter(prefix="/code-artifacts", tags=["Code Intelligence"])


@router.get("", response_model=CodeArtifactListResponse)
def list_code_artifacts(
    repository: Optional[str] = Query(None, description="Filter by repository name"),
    language: Optional[str] = Query(None, description="Filter by language"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List code artifacts persisted in PostgreSQL for current user with static code analysis."""
    query = db.query(CodeArtifact).filter(CodeArtifact.user_id == current_user.id)

    if repository:
        query = query.filter(CodeArtifact.repository.ilike(f"%{repository}%"))
    if language:
        query = query.filter(CodeArtifact.language.ilike(language))

    total = query.count()
    items = query.order_by(CodeArtifact.created_at.desc()).offset(offset).limit(limit).all()

    return CodeArtifactListResponse(
        items=[CodeArtifactSchema.model_validate(item) for item in items],
        total=total,
    )


@router.get("/{artifact_id}", response_model=CodeArtifactSchema)
def get_code_artifact_by_id(
    artifact_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve a single code artifact with source code and analysis."""
    artifact = db.query(CodeArtifact).filter(
        CodeArtifact.id == artifact_id, 
        CodeArtifact.user_id == current_user.id
    ).first()
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Code artifact with ID '{artifact_id}' not found.",
        )
    return CodeArtifactSchema.model_validate(artifact)


@router.get("/{artifact_id}/analysis", response_model=CodeAnalysisSchema)
def get_code_analysis_by_artifact_id(
    artifact_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve AST / static code analysis details for a specific artifact."""
    artifact = db.query(CodeArtifact).filter(
        CodeArtifact.id == artifact_id, 
        CodeArtifact.user_id == current_user.id
    ).first()
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Code analysis for artifact ID '{artifact_id}' not found.",
        )
        
    analysis = db.query(CodeAnalysis).filter(CodeAnalysis.code_artifact_id == artifact_id).first()
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Code analysis for artifact ID '{artifact_id}' not found.",
        )
    return CodeAnalysisSchema.model_validate(analysis)


@router.post("/analyze-github-file", response_model=CodeArtifactSchema)
async def analyze_github_file(
    payload: AnalyzeGitHubFileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch an accessible source file via GitHub REST API, perform AST static analysis, and persist to PostgreSQL."""
    owner = payload.owner.strip()
    repo = payload.repo.strip()
    path = payload.path.strip()
    full_repo_name = f"{owner}/{repo}"

    connector = GitHubConnector(auth_token=payload.auth_token)

    # 1. Fetch file content via GitHub REST API
    file_data = await connector.fetch_file_content(owner, repo, path)
    if not file_data or not file_data.get("code_content"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source file '{path}' in repository '{full_repo_name}' is inaccessible or empty.",
        )

    code_content = file_data["code_content"]
    size_bytes = file_data.get("size", len(code_content.encode("utf-8")))

    # 2. Get target user and platform connection
    user = current_user
    connection = (
        db.query(PlatformConnection)
        .filter(
            PlatformConnection.user_id == user.id,
            PlatformConnection.platform == "GitHub",
        )
        .first()
    )

    if not connection:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub account not connected. Please connect your GitHub account on the Platforms page.",
        )
        
    if connection.username.lower() != owner.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Repository owner '{owner}' does not match your connected GitHub username '{connection.username}'.",
        )

    # 3. Perform static AST analysis
    analyzer = CodeAnalyzerService()
    analysis_result = analyzer.analyze(path, code_content)
    language = analysis_result["language"]

    # 4. Save or update CodeArtifact in PostgreSQL
    artifact = (
        db.query(CodeArtifact)
        .filter(
            CodeArtifact.user_id == user.id,
            CodeArtifact.repository == full_repo_name,
            CodeArtifact.file_path == path,
        )
        .first()
    )

    if not artifact:
        artifact = CodeArtifact(
            user_id=user.id,
            platform_connection_id=connection.id,
            platform="GitHub",
            repository=full_repo_name,
            file_path=path,
            source_url=file_data.get("html_url"),
            commit_sha=file_data.get("sha"),
            language=language,
            code_content=code_content,
            size_bytes=size_bytes,
        )
        db.add(artifact)
        db.commit()
        db.refresh(artifact)
    else:
        artifact.code_content = code_content
        artifact.commit_sha = file_data.get("sha")
        artifact.size_bytes = size_bytes
        artifact.language = language
        db.commit()

    # 5. Save or update CodeAnalysis in PostgreSQL
    analysis = (
        db.query(CodeAnalysis)
        .filter(CodeAnalysis.code_artifact_id == artifact.id)
        .first()
    )

    if not analysis:
        analysis = CodeAnalysis(
            code_artifact_id=artifact.id,
            language=language,
            lines_of_code=analysis_result["lines_of_code"],
            function_count=analysis_result["function_count"],
            class_count=analysis_result["class_count"],
            cyclomatic_complexity=analysis_result["cyclomatic_complexity"],
            has_recursion=analysis_result["has_recursion"],
            detected_concepts=analysis_result["detected_concepts"],
            data_structures=analysis_result["data_structures"],
            analysis_summary=analysis_result["analysis_summary"],
        )
        db.add(analysis)
    else:
        analysis.language = language
        analysis.lines_of_code = analysis_result["lines_of_code"]
        analysis.function_count = analysis_result["function_count"]
        analysis.class_count = analysis_result["class_count"]
        analysis.cyclomatic_complexity = analysis_result["cyclomatic_complexity"]
        analysis.has_recursion = analysis_result["has_recursion"]
        analysis.detected_concepts = analysis_result["detected_concepts"]
        analysis.data_structures = analysis_result["data_structures"]
        analysis.analysis_summary = analysis_result["analysis_summary"]
        analysis.created_at = datetime.now(timezone.utc)

    db.commit()

    # 6. Emit normalized code analysis telemetry into Evidence table
    evidence_payload = analyzer.normalize_to_evidence(
        artifact_data={
            "id": artifact.id,
            "platform": "GitHub",
            "repository": full_repo_name,
            "file_path": path,
            "source_url": file_data.get("html_url"),
            "commit_sha": file_data.get("sha"),
            "created_at": artifact.created_at.isoformat() if artifact.created_at else None,
        },
        analysis_result=analysis_result,
    )

    evidence_record = Evidence(
        user_id=user.id,
        platform_connection_id=connection.id,
        external_id=file_data.get("sha"),
        title=evidence_payload["title"],
        evidence_type="code_analysis",
        raw_payload=evidence_payload["raw_payload"],
        normalized_payload=evidence_payload["normalized_payload"],
        occurred_at=datetime.now(timezone.utc),
    )
    db.add(evidence_record)
    db.commit()

    db.refresh(artifact)
    return CodeArtifactSchema.model_validate(artifact)
