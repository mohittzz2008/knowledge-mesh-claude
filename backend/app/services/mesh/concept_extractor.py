"""Concept Extractor & Evidence-to-Skill Assessment Mapping Service.

STRICT SEPARATION OF CONCERNS:
- EXTERNAL PROFILE: Only Evidence rows from platforms registered in the platform registry.
- INTERNAL PRACTICE: CodeLab CodeArtifacts are tracked separately and NEVER included
  in external developer skill assessments.
"""

from datetime import datetime, timezone
from typing import Any
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.skill import Skill, SkillAssessment
from app.models.code_artifact import CodeArtifact
from app.models.evidence import Evidence
from app.services.mesh.relationship_engine import seed_controlled_skills_and_relationships
from app.services.platform import external_platform_names


def get_external_platforms() -> set[str]:
    """Platforms whose Evidence rows count toward the EXTERNAL developer profile.

    Derived from the platform registry so a newly registered connector feeds the
    mesh, profile and graph automatically. CodeLab is intentionally excluded.
    """
    return external_platform_names()

# Concept string to Skill slug mapping
CONCEPT_TO_SKILL_SLUG = {
    "Functions": "functions",
    "Iteration": "iteration",
    "Object-Oriented Programming": "object-oriented-programming",
    "Error Handling": "error-handling",
    "Lists": "lists",
    "List": "lists",
    "Arrays": "arrays",
    "Array": "arrays",
    "List Comprehensions": "lists",
    "Dictionaries": "dictionaries",
    "Dict": "dictionaries",
    "Hash Table": "hashing",
    "Hashing": "hashing",
    "Dict Comprehensions": "dictionaries",
    "Sets": "sets",
    "Set": "sets",
    "Set Comprehensions": "sets",
    "Recursion": "recursion",
    "Tree": "tree-traversal",
    "Tree Traversal": "tree-traversal",
    "Tree/Graph Traversal": "tree-traversal",
    "Binary Tree": "tree-traversal",
    "Depth-First Search": "dfs",
    "DFS": "dfs",
    "Breadth-First Search": "dfs",
    "BFS": "dfs",
    "Async Programming": "async-programming",
    "Algorithms": "problem-solving",
    "Problem Solving": "problem-solving",
    "Competitive Programming": "problem-solving",
    "Data Structures": "lists",
    "Math": "problem-solving",
    "Python": "python",
    "python": "python",
    "C": "c",
    "c": "c",
    # Common tag spellings used by Codewars / GeeksforGeeks / LeetCode
    "Trees": "tree-traversal",
    "Graph": "graph-algorithms",
    "Graphs": "graph-algorithms",
    "Graph Theory": "graph-algorithms",
    "Hash Map": "hashing",
    "Hash Maps": "hashing",
    "Hash Tables": "hashing",
    "Hashes": "hashing",
    "Object-oriented Programming": "object-oriented-programming",
    "Exception Handling": "error-handling",
}

_NORMALIZED_SLUGS = {k.strip().lower(): v for k, v in CONCEPT_TO_SKILL_SLUG.items()}


def skill_slug_for(label: str) -> str:
    """Map a concept/tag label to a skill slug (case-insensitive, with a sane fallback)."""
    key = (label or "").strip().lower()
    return _NORMALIZED_SLUGS.get(key) or key.replace(" ", "-")


class ConceptExtractorService:
    """Extracts concepts from EXTERNAL Evidence to generate deterministic SkillAssessments.

    STRICT RULE: CodeLab CodeArtifacts are NEVER included in external skill assessments.
    Only Evidence rows from registered external platforms feed into the canonical
    external skill assessment. A profile with 0 solved problems contributes ZERO
    weight to any skill.
    """

    def extract_and_assess_user_skills(self, user_id: str, db: Session) -> list[SkillAssessment]:
        """Process ONLY external platform Evidence for skill assessment.

        CodeLab CodeArtifacts are completely excluded from this calculation.
        """
        skill_map = seed_controlled_skills_and_relationships(db)

        skill_evidence_ids: dict[str, set[str]] = {slug: set() for slug in skill_map.keys()}
        skill_weighted_scores: dict[str, float] = {slug: 0.0 for slug in skill_map.keys()}

        # ONLY query Evidence rows from EXTERNAL platforms that are ACTIVELY CONNECTED.
        # We load all Evidence for the user and then filter by platform.
        from app.models.platform import PlatformConnection
        all_evidence = (
            db.query(Evidence)
            .join(PlatformConnection, Evidence.platform_connection_id == PlatformConnection.id)
            .filter(Evidence.user_id == user_id, PlatformConnection.connected == True)
            .all()
        )

        external_platforms = get_external_platforms()
        for ev in all_evidence:
            # Strictly filter to external platforms only.
            platform = ev.platform_connection.platform if ev.platform_connection else None
            if platform not in external_platforms:
                # Skip CodeLab evidence and any unattributed rows.
                continue

            payload = ev.normalized_payload or {}
            raw_payload = ev.raw_payload or {}
            ev_skills = payload.get("skills", [])
            ev_type = ev.evidence_type or "activity"

            # Domain isolation for badges: attribute strictly to the badge's own domain
            if ev_type == "badge":
                badge_name = payload.get("badge_name")
                if badge_name:
                    ev_skills = [badge_name]

            # Determine evidence weight by type and verified quality indicators.
            if ev_type in ["code_file", "code_analysis"]:
                weight = 2.0
            elif ev_type == "problem_submission":
                weight = 1.5
            elif ev_type == "badge":
                # Scale weight according to verified badge stars/tier (1 to 5/6 stars)
                stars_val = payload.get("stars") or raw_payload.get("stars") or 1
                try:
                    stars = int(stars_val)
                except (ValueError, TypeError):
                    stars = 1
                weight = min(3.5, max(1.0, 1.0 + (stars - 1) * 0.5))
            elif ev_type in ["profile", "problem_solving_summary"]:
                # Verified active solver profile with solved challenges or positive level
                total_solved = payload.get("total_solved") or raw_payload.get("total_solved") or 0
                level = payload.get("level") or raw_payload.get("level") or 0
                weight = 1.0 if (total_solved > 0 or level > 0) else 0.0
            elif ev_type == "topic_statistics":
                problems_solved = payload.get("problems_solved") or 0
                weight = min(5.0, float(problems_solved) * 0.5) if problems_solved > 0 else 0.0
            elif ev_type == "code_lab_attempt":
                weight = 0.0
            else:
                weight = 0.5

            seen_slugs = set()
            for sk_label in ev_skills:
                slug = skill_slug_for(sk_label)
                if slug in skill_evidence_ids and weight > 0 and slug not in seen_slugs:
                    seen_slugs.add(slug)
                    skill_evidence_ids[slug].add(ev.id)
                    skill_weighted_scores[slug] += weight

        assessments: list[SkillAssessment] = []

        for slug, skill in skill_map.items():
            evidence_count = len(skill_evidence_ids[slug])
            w_score = skill_weighted_scores[slug]

            # Deterministic external mastery from real evidence only.
            if evidence_count == 0:
                mastery_score = 0.0
                status = "NO_EVIDENCE"
            else:
                # Quality-weighted mastery with conservative, bounded count scaling (ratio 3:1 in favor of weight)
                raw_score = (w_score * 7.5) + (evidence_count * 2.5)
                mastery_score = min(100.0, round(raw_score, 1))

                if mastery_score < 30.0:
                    status = "weak"
                elif mastery_score < 75.0:
                    status = "developing"
                else:
                    status = "mastered"

            assessment = (
                db.query(SkillAssessment)
                .filter(
                    SkillAssessment.user_id == user_id,
                    SkillAssessment.skill_id == skill.id,
                )
                .order_by(SkillAssessment.evaluated_at.desc(), SkillAssessment.id.desc())
                .first()
            )

            if not assessment:
                assessment = SkillAssessment(
                    user_id=user_id,
                    skill_id=skill.id,
                    mastery_score=mastery_score,
                    status=status,
                    evidence_count=evidence_count,
                    evaluated_at=datetime.now(timezone.utc),
                )
                db.add(assessment)
            else:
                assessment.mastery_score = mastery_score
                assessment.status = status
                assessment.evidence_count = evidence_count
                assessment.evaluated_at = datetime.now(timezone.utc)

            assessments.append(assessment)

        db.commit()
        return assessments
