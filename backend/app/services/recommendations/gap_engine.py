"""Knowledge Gap Selection Engine based on Prerequisite Traversal."""

from typing import Any, Optional
from sqlalchemy.orm import Session
from app.models.skill import Skill, SkillRelationship, SkillAssessment, get_latest_user_assessments
from app.services.mesh.relationship_engine import seed_controlled_skills_and_relationships


class KnowledgeGapEngine:
    """Selects actionable skill gaps considering prerequisite chains, evidence strength, and confidence."""

    def find_actionable_gaps(self, user_id: str, db: Session) -> list[dict[str, Any]]:
        """Identify actionable skill gaps by evaluating prerequisite readiness."""
        skill_map = seed_controlled_skills_and_relationships(db)
        skills = list(skill_map.values())
        skill_by_id = {s.id: s for s in skills}
        skill_by_slug = {s.slug: s for s in skills}

        latest_assessments_by_id = get_latest_user_assessments(db, user_id)
        assessment_by_slug = {
            skill_by_id[sk_id].slug: a
            for sk_id, a in latest_assessments_by_id.items()
            if sk_id in skill_by_id
        }

        # Query parent relationships (prerequisites)
        relationships = db.query(SkillRelationship).filter(SkillRelationship.relationship_type == "prerequisite").all()
        prereqs_for_skill: dict[str, list[str]] = {s.slug: [] for s in skills}

        for rel in relationships:
            p_skill = skill_by_id.get(rel.parent_skill_id)
            c_skill = skill_by_id.get(rel.child_skill_id)
            if p_skill and c_skill:
                prereqs_for_skill[c_skill.slug].append(p_skill.slug)

        actionable_gaps = []

        for slug, skill in skill_by_slug.items():
            ass = assessment_by_slug.get(slug)
            status = ass.status if ass else "NO_EVIDENCE"
            ev_count = ass.evidence_count if ass else 0

            # Gap candidate if status is weak or developing or NO_EVIDENCE
            if status in ["weak", "developing", "NO_EVIDENCE"]:
                prereq_slugs = prereqs_for_skill.get(slug, [])
                prereqs_satisfied = True
                weak_prereqs = []

                for p_slug in prereq_slugs:
                    p_ass = assessment_by_slug.get(p_slug)
                    p_status = p_ass.status if p_ass else "NO_EVIDENCE"
                    if p_status in ["weak", "NO_EVIDENCE"]:
                        prereqs_satisfied = False
                        weak_prereqs.append(p_slug)

                # Prioritize skills whose prerequisites are satisfied (prerequisite readiness principle)
                priority_score = 100 if prereqs_satisfied else 30
                if status == "weak":
                    priority_score += 40
                elif status == "developing":
                    priority_score += 20
                elif status == "NO_EVIDENCE" and not prereq_slugs:
                    priority_score += 50

                actionable_gaps.append({
                    "skill_id": skill.id,
                    "slug": skill.slug,
                    "name": skill.name,
                    "category": skill.category,
                    "status": status,
                    "evidence_count": ev_count,
                    "prereqs_satisfied": prereqs_satisfied,
                    "prerequisites": [skill_by_slug[p].name for p in prereq_slugs if p in skill_by_slug],
                    "weak_prerequisites": [skill_by_slug[p].name for p in weak_prereqs if p in skill_by_slug],
                    "priority_score": priority_score,
                })

        # Sort gaps by priority_score descending
        actionable_gaps.sort(key=lambda g: g["priority_score"], reverse=True)
        return actionable_gaps
