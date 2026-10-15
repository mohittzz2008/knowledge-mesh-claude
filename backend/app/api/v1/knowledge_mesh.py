"""API endpoints for Dynamic Knowledge Mesh Graph and Skill Evidence Telemetry."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.skill import Skill, SkillRelationship, SkillAssessment
from app.models.code_artifact import CodeArtifact
from app.api.v1.auth import get_current_user
from app.schemas.knowledge_mesh import (
    KnowledgeMeshResponse,
    SkillDetailResponse,
    CodeArtifactLinkSchema,
)
from app.services.mesh.graph_builder import KnowledgeMeshGraphBuilder
from app.services.mesh.concept_extractor import CONCEPT_TO_SKILL_SLUG, ConceptExtractorService

router = APIRouter(prefix="/knowledge-mesh", tags=["Knowledge Mesh"])


@router.get("", response_model=KnowledgeMeshResponse)
def get_knowledge_mesh(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve live Knowledge Mesh graph (nodes & edges) built from PostgreSQL code telemetry for current user."""
    builder = KnowledgeMeshGraphBuilder()
    graph_data = builder.build_graph(current_user.id, db)
    return KnowledgeMeshResponse.model_validate(graph_data)


@router.get("/skills/{skill_identifier}", response_model=SkillDetailResponse)
def get_skill_detail_and_evidence(
    skill_identifier: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve detailed evidence breakdown for a specific skill node by ID or slug."""
    # 1. Lookup skill by slug or id
    skill = (
        db.query(Skill)
        .filter((Skill.slug == skill_identifier) | (Skill.id == skill_identifier))
        .first()
    )

    if not skill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill '{skill_identifier}' not found in Knowledge Mesh taxonomy.",
        )

    # 2. Get assessment for current user
    assessment = (
        db.query(SkillAssessment)
        .filter(
            SkillAssessment.user_id == current_user.id,
            SkillAssessment.skill_id == skill.id,
        )
        .order_by(SkillAssessment.evaluated_at.desc(), SkillAssessment.id.desc())
        .first()
    )

    # 3. Get prerequisites & related skills
    parent_rels = (
        db.query(SkillRelationship)
        .filter(SkillRelationship.child_skill_id == skill.id)
        .all()
    )
    child_rels = (
        db.query(SkillRelationship)
        .filter(SkillRelationship.parent_skill_id == skill.id)
        .all()
    )

    prerequisites = []
    for r in parent_rels:
        p_skill = db.query(Skill).filter(Skill.id == r.parent_skill_id).first()
        if p_skill:
            prerequisites.append(p_skill.name)

    related_skills = []
    for r in child_rels:
        c_skill = db.query(Skill).filter(Skill.id == r.child_skill_id).first()
        if c_skill:
            related_skills.append(c_skill.name)

    # 4. Find linked code artifacts for current user
    artifacts = db.query(CodeArtifact).filter(CodeArtifact.user_id == current_user.id).all()
    linked_artifacts = []

    for artifact in artifacts:
        if not artifact.analysis:
            continue

        concepts = artifact.analysis.detected_concepts or []
        data_structs = artifact.analysis.data_structures or []
        tags = set(concepts + data_structs)

        matched_slugs = [CONCEPT_TO_SKILL_SLUG.get(t) for t in tags]
        if skill.slug in matched_slugs:
            linked_artifacts.append(
                CodeArtifactLinkSchema(
                    id=artifact.id,
                    repository=artifact.repository,
                    file_path=artifact.file_path,
                    language=artifact.language,
                    source_url=artifact.source_url,
                    lines_of_code=artifact.analysis.lines_of_code if artifact.analysis else 0,
                    has_recursion=artifact.analysis.has_recursion if artifact.analysis else False,
                    created_at=artifact.created_at.isoformat() if artifact.created_at else None,
                )
            )

    ev_count = assessment.evidence_count if assessment else 0
    mastery = round(assessment.mastery_score, 1) if assessment else 0.0
    status_text = assessment.status if assessment else "insufficient"

    explanation = (
        f"Knowledge Mesh verified {ev_count} source file(s) for '{skill.name}'. "
        f"Status: {status_text.upper()} ({mastery}% evidence score)."
        if ev_count > 0
        else f"No source code evidence ingested for '{skill.name}' yet."
    )

    return SkillDetailResponse(
        skill_id=skill.id,
        name=skill.name,
        slug=skill.slug,
        category=skill.category,
        description=skill.description,
        status=status_text,
        mastery_score=mastery,
        evidence_count=ev_count,
        prerequisites=prerequisites,
        related_skills=related_skills,
        artifacts=linked_artifacts,
        explanation=explanation,
    )


@router.post("/rebuild")
def rebuild_knowledge_mesh(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Re-evaluate concept extraction and skill assessments across PostgreSQL code artifacts for current user."""
    extractor = ConceptExtractorService()
    assessments = extractor.extract_and_assess_user_skills(current_user.id, db)
    return {
        "message": f"Successfully re-evaluated {len(assessments)} skill assessments in PostgreSQL.",
        "user_id": current_user.id,
    }
