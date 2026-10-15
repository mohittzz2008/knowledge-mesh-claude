"""Pydantic schemas for AI Coach APIs."""

from typing import Optional, Any
from pydantic import BaseModel


class EvidenceReferenceSchema(BaseModel):
    title: str
    platform: str
    repository: Optional[str] = None
    file_path: Optional[str] = None
    source_url: Optional[str] = None


class SuggestedActionSchema(BaseModel):
    label: str
    action_type: str  # 'mesh' | 'learning_path' | 'code_intelligence' | 'platforms' | 'codelab'
    target_path: str
    target_id: Optional[str] = None


class CoachMessageCreate(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    skill_id: Optional[str] = None
    code_artifact_id: Optional[str] = None


class CoachMessageResponse(BaseModel):
    conversation_id: str
    message_id: str
    answer: str
    intent: Optional[str] = "GENERAL"
    confidence: Optional[float] = 0.0
    context_used: Optional[dict[str, Any]] = None
    evidence_references: list[EvidenceReferenceSchema] = []
    suggested_actions: list[SuggestedActionSchema] = []
    detected_mistake_patterns: list[dict[str, Any]] = []
    
    # Structured AI response fields (Phase 5)
    language: Optional[str] = None
    corrected_code: Optional[str] = None
    approach: Optional[str] = None
    complexity: Optional[dict[str, str]] = None
    bugs: list[str] = []
    edge_cases: list[str] = []
    comparison: list[str] = []
    grounding: Optional[dict[str, Any]] = None

    created_at: str


class CoachMessageItemSchema(BaseModel):
    id: str
    sender: str
    content: str
    intent: Optional[str] = "GENERAL"
    confidence: Optional[float] = 0.0
    context_used: Optional[dict[str, Any]] = None
    evidence_references: list[EvidenceReferenceSchema] = []
    suggested_actions: list[SuggestedActionSchema] = []
    detected_mistake_patterns: list[dict[str, Any]] = []
    
    # Structured AI response fields (Phase 5)
    language: Optional[str] = None
    corrected_code: Optional[str] = None
    approach: Optional[str] = None
    complexity: Optional[dict[str, str]] = None
    bugs: list[str] = []
    edge_cases: list[str] = []
    comparison: list[str] = []
    grounding: Optional[dict[str, Any]] = None

    created_at: Optional[str] = None


class CoachConversationSchema(BaseModel):
    id: str
    title: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    message_count: int = 0


class CoachConversationDetailResponse(BaseModel):
    id: str
    title: str
    created_at: Optional[str] = None
    messages: list[CoachMessageItemSchema] = []


class AnalyzeLogicRequest(BaseModel):
    code: str
    language: str


class AnalyzeLogicResponse(BaseModel):
    summary: str
    execution_flow: str
    time_complexity: str
    space_complexity: str
    bugs: list[str]
    edge_cases: list[str]
    improvement_opportunities: list[str]


class CompareApproachRequest(BaseModel):
    problem: str
    approach_a: str
    approach_b: str
    language: str


class CompareApproachResponse(BaseModel):
    recommended_approach: str
    explanation: str
    approach_a_time_complexity: str
    approach_a_space_complexity: str
    approach_b_time_complexity: str
    approach_b_space_complexity: str
    correctness: str
    readability: str
