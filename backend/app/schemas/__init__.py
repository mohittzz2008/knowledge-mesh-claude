"""Schemas module initialization."""

from app.schemas.platform import (
    PlatformValidateRequest,
    PlatformValidateResponse,
    PlatformSyncRequest,
    PlatformSyncResponse,
    PlatformRegistryItemSchema,
)
from app.schemas.evidence import EvidenceItemSchema, EvidenceListResponse
from app.schemas.code_artifact import (
    CodeArtifactSchema,
    CodeAnalysisSchema,
    CodeArtifactListResponse,
    AnalyzeGitHubFileRequest,
)
from app.schemas.knowledge_mesh import (
    KnowledgeMeshNode,
    KnowledgeMeshEdge,
    KnowledgeMeshResponse,
    SkillDetailResponse,
)
from app.schemas.recommendation import (
    NextBestActionResponse,
    PracticeRecommendationSchema,
    PracticeRecommendationListResponse,
    LearningPathStepSchema,
    LearningPathResponse,
)
from app.schemas.coach import (
    CoachMessageCreate,
    CoachMessageResponse,
    CoachConversationSchema,
    CoachConversationDetailResponse,
)
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
from app.schemas.user import UserProfileResponse

__all__ = [
    "PlatformValidateRequest",
    "PlatformValidateResponse",
    "PlatformSyncRequest",
    "PlatformSyncResponse",
    "PlatformRegistryItemSchema",
    "EvidenceItemSchema",
    "EvidenceListResponse",
    "CodeArtifactSchema",
    "CodeAnalysisSchema",
    "CodeArtifactListResponse",
    "AnalyzeGitHubFileRequest",
    "KnowledgeMeshNode",
    "KnowledgeMeshEdge",
    "KnowledgeMeshResponse",
    "SkillDetailResponse",
    "NextBestActionResponse",
    "PracticeRecommendationSchema",
    "PracticeRecommendationListResponse",
    "LearningPathStepSchema",
    "LearningPathResponse",
    "CoachMessageCreate",
    "CoachMessageResponse",
    "CoachConversationSchema",
    "CoachConversationDetailResponse",
    "CodeRunRequest",
    "CodeRunResponse",
    "CodeAnalyzeRequest",
    "CodeAnalyzeResponse",
    "CodeSubmitRequest",
    "CodeSubmitResponse",
    "CodeHintRequest",
    "CodeHintResponse",
    "UserProfileResponse",
]
