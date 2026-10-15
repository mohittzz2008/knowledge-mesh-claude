"""Pydantic schemas for CodeArtifact and CodeAnalysis APIs."""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class CodeAnalysisSchema(BaseModel):
    id: str
    code_artifact_id: str
    language: str
    lines_of_code: int
    function_count: int
    class_count: int
    cyclomatic_complexity: int
    has_recursion: bool
    detected_concepts: Optional[list[str]] = None
    data_structures: Optional[list[str]] = None
    analysis_summary: Optional[dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CodeArtifactSchema(BaseModel):
    id: str
    user_id: str
    platform_connection_id: str
    platform: str
    repository: str
    file_path: str
    source_url: Optional[str] = None
    commit_sha: Optional[str] = None
    language: str
    code_content: str
    size_bytes: int
    created_at: datetime
    analysis: Optional[CodeAnalysisSchema] = None

    class Config:
        from_attributes = True


class CodeArtifactListResponse(BaseModel):
    items: list[CodeArtifactSchema]
    total: int


class AnalyzeGitHubFileRequest(BaseModel):
    owner: str = Field(..., description="GitHub repository owner")
    repo: str = Field(..., description="GitHub repository name")
    path: str = Field(..., description="Relative file path in repository (e.g. app/main.py)")
    auth_token: Optional[str] = Field(None, description="Optional GitHub OAuth token")
