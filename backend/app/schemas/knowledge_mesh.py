"""Pydantic schemas for Knowledge Mesh Graph and Skill Evidence APIs."""

from typing import Any, Optional
from pydantic import BaseModel


class CodeArtifactLinkSchema(BaseModel):
    id: str
    repository: str
    file_path: str
    language: str
    source_url: Optional[str] = None
    lines_of_code: int = 0
    has_recursion: bool = False
    created_at: Optional[str] = None


class KnowledgeMeshNodeData(BaseModel):
    skill_id: str
    name: str
    slug: str
    category: str
    mastery: float
    status: str  # 'mastered' | 'developing' | 'weak' | 'insufficient'
    evidenceCount: int
    evidenceStrength: str  # 'Strong' | 'Moderate' | 'Limited' | 'None'
    confidence: float
    description: Optional[str] = None
    sources: list[str] = []
    linkedArtifacts: list[CodeArtifactLinkSchema] = []
    explanation: str
    recentActivity: str
    recommendation: str


class KnowledgeMeshNode(BaseModel):
    id: str
    type: str = "skillNode"
    position: dict[str, int]
    data: KnowledgeMeshNodeData


class KnowledgeMeshEdge(BaseModel):
    id: str
    source: str
    target: str
    relationship_type: str
    animated: bool = False
    style: Optional[dict[str, Any]] = None


class KnowledgeMeshResponse(BaseModel):
    user_id: str
    nodes: list[KnowledgeMeshNode]
    edges: list[KnowledgeMeshEdge]
    total_skills: int
    assessed_skills_count: int


class SkillDetailResponse(BaseModel):
    skill_id: str
    name: str
    slug: str
    category: str
    description: Optional[str] = None
    status: str
    mastery_score: float
    evidence_count: int
    prerequisites: list[str] = []
    related_skills: list[str] = []
    artifacts: list[CodeArtifactLinkSchema] = []
    explanation: str
