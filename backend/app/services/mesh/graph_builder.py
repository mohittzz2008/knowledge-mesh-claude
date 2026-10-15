"""Knowledge Mesh Graph Builder Service."""

from typing import Any
from sqlalchemy.orm import Session
from app.models.skill import Skill, SkillRelationship, SkillAssessment, get_latest_user_assessments
from app.models.code_artifact import CodeArtifact, CodeAnalysis
from app.models.evidence import Evidence
from app.models.platform import PlatformConnection
from app.services.mesh.concept_extractor import (
    CONCEPT_TO_SKILL_SLUG,
    ConceptExtractorService,
    get_external_platforms,
    skill_slug_for,
)
from app.services.mesh.relationship_engine import seed_controlled_skills_and_relationships

# Standard 2D layout grid positions for React Flow graph visualization
LAYOUT_POSITIONS: dict[str, dict[str, int]] = {
    "problem-solving": {"x": -100, "y": 40},
    "functions": {"x": 250, "y": 40},
    "python": {"x": 450, "y": 40},
    "c": {"x": 650, "y": 40},
    "iteration": {"x": 50, "y": 140},
    "lists": {"x": 250, "y": 140},
    "dictionaries": {"x": 450, "y": 140},
    "sets": {"x": 650, "y": 140},
    "arrays": {"x": 150, "y": 260},
    "hashing": {"x": 550, "y": 260},
    "object-oriented-programming": {"x": -100, "y": 260},
    "error-handling": {"x": 750, "y": 260},
    "recursion": {"x": 250, "y": 380},
    "async-programming": {"x": 750, "y": 380},
    "tree-traversal": {"x": 150, "y": 500},
    "dfs": {"x": 350, "y": 500},
    "graph-algorithms": {"x": 250, "y": 620},
}


class KnowledgeMeshGraphBuilder:
    """Builds live React Flow compatible Knowledge Mesh graph from PostgreSQL telemetry."""

    def build_graph(self, user_id: str, db: Session) -> dict[str, Any]:
        """Build node, edge, and evidence telemetry payload."""
        # 1. Ensure skills and assessments are up to date
        extractor = ConceptExtractorService()
        extractor.extract_and_assess_user_skills(user_id, db)

        skills = db.query(Skill).all()
        skill_by_id = {s.id: s for s in skills}
        skill_by_slug = {s.slug: s for s in skills}

        assessment_by_skill_id = get_latest_user_assessments(db, user_id)

        # 2. Query evidence & code artifacts for node-to-code explainability & platform provenance
        artifacts = db.query(CodeArtifact).filter(CodeArtifact.user_id == user_id).all()
        # Only evidence from currently-connected platforms counts (matches the extractor).
        evidence_items = (
            db.query(Evidence)
            .join(PlatformConnection, Evidence.platform_connection_id == PlatformConnection.id)
            .filter(Evidence.user_id == user_id, PlatformConnection.connected == True)  # noqa: E712
            .all()
        )
        
        artifacts_by_skill_slug: dict[str, list[dict[str, Any]]] = {s.slug: [] for s in skills}
        sources_by_skill_slug: dict[str, set[str]] = {s.slug: set() for s in skills}

        for artifact in artifacts:
            if not artifact.analysis:
                continue
            # Skip CodeLab artifacts — they are internal practice, not external platform data.
            if (artifact.platform or "").upper() == "CODELAB":
                continue

            concepts = artifact.analysis.detected_concepts or []
            data_structs = artifact.analysis.data_structures or []
            tags = set(concepts + data_structs)

            for tag in tags:
                slug = CONCEPT_TO_SKILL_SLUG.get(tag)
                if slug and slug in artifacts_by_skill_slug:
                    sources_by_skill_slug[slug].add(artifact.platform or "GitHub")
                    # Avoid duplicates per artifact
                    if not any(item["id"] == artifact.id for item in artifacts_by_skill_slug[slug]):
                        artifacts_by_skill_slug[slug].append({
                            "id": artifact.id,
                            "repository": artifact.repository,
                            "file_path": artifact.file_path,
                            "language": artifact.language,
                            "source_url": artifact.source_url,
                            "lines_of_code": artifact.analysis.lines_of_code if artifact.analysis else 0,
                            "has_recursion": artifact.analysis.has_recursion if artifact.analysis else False,
                            "created_at": artifact.created_at.isoformat() if artifact.created_at else None,
                        })

        external_platforms = get_external_platforms()
        for ev in evidence_items:
            # Skip code_lab_attempt rows and unattributed evidence
            if (ev.evidence_type or "") == "code_lab_attempt":
                continue
            plt = ev.platform_connection.platform if ev.platform_connection else None
            if plt not in external_platforms:
                continue
            payload = ev.normalized_payload or {}
            ev_skills = payload.get("skills", [])
            if (ev.evidence_type or "") == "badge":
                badge_name = payload.get("badge_name")
                if badge_name:
                    ev_skills = [badge_name]
            for sk_label in ev_skills:
                slug = skill_slug_for(sk_label)
                if slug in sources_by_skill_slug:
                    sources_by_skill_slug[slug].add(plt)

        # 3. Construct React Flow nodes
        nodes = []
        for slug, skill in skill_by_slug.items():
            pos = LAYOUT_POSITIONS.get(slug, {"x": 250, "y": 300})
            assessment = assessment_by_skill_id.get(skill.id)

            ev_count = assessment.evidence_count if assessment else 0
            mastery = round(assessment.mastery_score, 1) if assessment else 0.0
            status = assessment.status if assessment else "insufficient"

            if ev_count >= 5:
                strength = "Strong"
            elif ev_count >= 2:
                strength = "Moderate"
            elif ev_count == 1:
                strength = "Limited"
            else:
                strength = "None"

            linked_arts = artifacts_by_skill_slug.get(slug, [])
            repos_set = sorted(list(set(a["repository"] for a in linked_arts)))

            explanation = (
                f"Traceable to {ev_count} verified source file(s) in repository '{repos_set[0]}'."
                if repos_set
                else (f"Based on {ev_count} imported item{'' if ev_count == 1 else 's'} from your connected platforms." if ev_count > 0 else "Nothing imported for this skill yet.")
            )

            dedup_sources = sorted(list(sources_by_skill_slug.get(slug, set())))

            nodes.append({
                "id": slug,
                "type": "skillNode",
                "position": pos,
                "data": {
                    "skill_id": skill.id,
                    "name": skill.name,
                    "slug": skill.slug,
                    "category": skill.category,
                    "mastery": mastery,
                    "status": status,
                    "evidenceCount": ev_count,
                    "evidenceStrength": strength,
                    "confidence": min(1.0, 0.3 + (ev_count * 0.1)) if ev_count > 0 else 0.0,
                    "description": skill.description,
                    "sources": dedup_sources,
                    "linkedArtifacts": linked_arts,
                    "explanation": explanation,
                    "recentActivity": f"Detected across {len(dedup_sources)} platform(s)" if dedup_sources else "No recent activity",
                    "recommendation": f"Practice {skill.name} fundamentals" if status in ["weak", "insufficient"] else f"Solid evidence for {skill.name}",
                },
            })

        # 4. Construct React Flow edges from skill_relationships table
        relationships = db.query(SkillRelationship).all()
        edges = []
        for rel in relationships:
            parent_skill = skill_by_id.get(rel.parent_skill_id)
            child_skill = skill_by_id.get(rel.child_skill_id)

            if parent_skill and child_skill:
                edge_id = f"e-{parent_skill.slug}-{child_skill.slug}"
                
                c_assessment = assessment_by_skill_id.get(child_skill.id)
                c_status = c_assessment.status if c_assessment else "insufficient"
                
                stroke_color = "#F59E0B" if c_status in ["weak", "insufficient"] else "#7C3AED"

                edges.append({
                    "id": edge_id,
                    "source": parent_skill.slug,
                    "target": child_skill.slug,
                    "relationship_type": rel.relationship_type,
                    "animated": c_status in ["weak", "insufficient"],
                    "style": {
                        "stroke": stroke_color,
                        "strokeWidth": 2,
                    },
                })

        return {
            "user_id": user_id,
            "nodes": nodes,
            "edges": edges,
            "total_skills": len(nodes),
            "assessed_skills_count": len([n for n in nodes if n["data"]["evidenceCount"] > 0]),
        }
