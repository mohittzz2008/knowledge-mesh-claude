"""Dynamic Learning Path Roadmap Generator."""

from typing import Any
from sqlalchemy.orm import Session
from app.models.platform import PlatformConnection
from app.models.evidence import Evidence
from app.models.skill import Skill, SkillRelationship, SkillAssessment, get_latest_user_assessments
from app.services.mesh.relationship_engine import seed_controlled_skills_and_relationships
from app.services.mesh.concept_extractor import CONCEPT_TO_SKILL_SLUG


class LearningPathGenerator:
    """Generates dynamic learning path roadmaps traceable to real user evidence."""

    def generate_roadmap(self, user_id: str, db: Session) -> dict[str, Any]:
        """Build dynamic learning roadmap steps from PostgreSQL telemetry."""
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

        # Query user's connected platforms to establish platform awareness
        active_conns = (
            db.query(PlatformConnection)
            .filter(PlatformConnection.user_id == user_id, PlatformConnection.connected == True)
            .all()
        )
        user_platforms = {c.platform for c in active_conns}

        # Map skill slug to demonstrating platforms from user's active evidence
        all_evidence = (
            db.query(Evidence)
            .join(PlatformConnection, Evidence.platform_connection_id == PlatformConnection.id)
            .filter(Evidence.user_id == user_id, PlatformConnection.connected == True)
            .all()
        )
        platforms_by_slug: dict[str, set[str]] = {s.slug: set() for s in skills}
        for ev in all_evidence:
            plat = ev.platform_connection.platform if ev.platform_connection else None
            if not plat:
                continue
            payload = ev.normalized_payload or {}
            ev_skills = payload.get("skills", [])
            for sk in ev_skills:
                sk_slug = CONCEPT_TO_SKILL_SLUG.get(sk) or sk.lower().replace(" ", "-")
                if sk_slug in platforms_by_slug:
                    platforms_by_slug[sk_slug].add(plat)

        # Query prerequisite relationships
        prereqs_db = db.query(SkillRelationship).filter(SkillRelationship.relationship_type == "prerequisite").all()
        prereq_slugs_by_child: dict[str, list[str]] = {s.slug: [] for s in skills}
        for rel in prereqs_db:
            p_skill = skill_by_id.get(rel.parent_skill_id)
            c_skill = skill_by_id.get(rel.child_skill_id)
            if p_skill and c_skill:
                prereq_slugs_by_child[c_skill.slug].append(p_skill.slug)

        # Sequence order: Core foundations → Language skills → Advanced algorithms
        # All 17 controlled skills are included so evidence for any tracked skill
        # is reflected in the user's learning path.
        ordered_slugs = [
            # Core foundations
            "functions",
            "iteration",
            "lists",
            "dictionaries",
            "sets",
            "arrays",
            "hashing",
            "object-oriented-programming",
            "error-handling",
            # Language proficiency
            "python",
            "c",
            # Advanced algorithms
            "problem-solving",
            "recursion",
            "tree-traversal",
            "dfs",
            "async-programming",
            "graph-algorithms",
        ]

        steps = []
        total_ev_count = sum(a.evidence_count for a in assessment_by_slug.values())
        recommended_assigned = False

        for idx, slug in enumerate(ordered_slugs, start=1):
            skill = skill_by_slug.get(slug)
            if not skill:
                continue

            ass = assessment_by_slug.get(slug)
            ev_count = ass.evidence_count if ass else 0
            mastery = round(ass.mastery_score) if ass else 0
            status_raw = ass.status if ass else "NO_EVIDENCE"

            # Derive practice source dynamically from evidence provenance and active connections
            demonstrating = platforms_by_slug.get(slug, set())
            if demonstrating:
                practice_source = " & ".join(sorted(demonstrating))
            elif len(user_platforms - {"GitHub"}) == 1:
                # Exactly one problem-solving platform connected: point at it by name.
                practice_source = next(iter(user_platforms - {"GitHub"}))
            elif user_platforms:
                practice_source = "connected platforms"
            else:
                practice_source = "Code Lab"

            if ev_count > 0 and (status_raw == "mastered" or mastery >= 75):
                step_status = "completed"
                category = "Foundation"
                why = f"Verified with {ev_count} evidence item(s)."
            elif ev_count > 0 and (status_raw in ["weak", "developing"] or mastery < 75):
                step_status = "in_progress"
                category = "Current Focus"
                why = f"Active focus area with {ev_count} evidence item(s). Strengthening this resolves key prerequisite gaps."
            elif total_ev_count == 0:
                if idx == 1:
                    step_status = "in_progress"
                    category = "Initial Focus"
                    why = "No verified skill evidence for this skill yet. Practice or sync to build evidence."
                else:
                    step_status = "locked"
                    category = "Future Goal"
                    why = "Requires prerequisite evidence building."
            else:
                # Skill has no evidence yet. Evaluate prerequisite readiness
                prereqs = prereq_slugs_by_child.get(slug, [])
                prereqs_satisfied = True
                for p_slug in prereqs:
                    p_ass = assessment_by_slug.get(p_slug)
                    if not p_ass or p_ass.evidence_count == 0:
                        prereqs_satisfied = False
                        break

                if prereqs_satisfied and not recommended_assigned:
                    recommended_assigned = True
                    step_status = "recommended"
                    category = "Next"
                    why = f"Recommended next milestone. Build initial evidence for {skill.name} to advance along your learning path."
                else:
                    step_status = "locked"
                    category = "Future Goal"
                    why = "Requires prerequisite milestone completion."

            steps.append({
                "id": f"step-{slug}",
                "step_number": idx,
                "title": skill.name,
                "slug": skill.slug,
                "category": category,
                "status": step_status,
                "mastery": mastery,
                "evidence_count": ev_count,
                "why": why,
                "prerequisites": [skill_by_slug[p].name for p in prereq_slugs_by_child.get(slug, []) if p in skill_by_slug],
                "recommended_practice": f"Practice {skill.name} on {practice_source}",
            })

        if total_ev_count == 0:
            current_focus_title = "No verified skill evidence yet."
        else:
            current_focus = next((s for s in steps if s["status"] == "in_progress"), steps[0])
            current_focus_title = current_focus["title"]

        return {
            "user_id": user_id,
            "target_goal": "Graph Algorithms & Tree Shortest Paths",
            "current_focus_skill": current_focus_title,
            "steps": steps,
            "total_steps": len(steps),
        }
