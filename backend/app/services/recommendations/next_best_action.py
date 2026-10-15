"""Next Best Action Service Engine."""

from typing import Any, Optional
from sqlalchemy.orm import Session
from app.services.recommendations.gap_engine import KnowledgeGapEngine


class NextBestActionService:
    """Determines the user's current Next Best Action with evidence justification."""

    def get_next_best_action(self, user_id: str, db: Session) -> dict[str, Any]:
        return self.determine_next_best_action(user_id, db)

    def determine_next_best_action(self, user_id: str, db: Session) -> dict[str, Any]:
        """Determine next best learning action based on Knowledge Mesh state."""
        gap_engine = KnowledgeGapEngine()
        gaps = gap_engine.find_actionable_gaps(user_id, db)

        if not gaps:
            # Dynamically select highest scored skill, or a fallback if user has absolutely no evidence yet.
            from app.models.skill import SkillAssessment, Skill
            highest = (
                db.query(SkillAssessment)
                .join(Skill, SkillAssessment.skill_id == Skill.id)
                .filter(SkillAssessment.user_id == user_id, SkillAssessment.status != "NO_EVIDENCE")
                .order_by(SkillAssessment.mastery_score.desc())
                .first()
            )
            
            if highest:
                return {
                    "target_skill": highest.skill.name,
                    "slug": highest.skill.slug,
                    "reason": f"You have mastered your prerequisites! Continue practicing {highest.skill.name} or start a new track.",
                    "evidence_count": highest.evidence_count,
                    "recommended_difficulty": "Hard",
                    "learning_objective": f"Push your limits in {highest.skill.name}.",
                    "prerequisites": [],
                    "has_sufficient_evidence": True,
                }
            else:
                return {
                    "target_skill": "Functions",
                    "slug": "functions",
                    "reason": "No verified skill evidence yet. Connect a platform or practice a CodeLab problem to unlock personalized recommendations.",
                    "evidence_count": 0,
                    "recommended_difficulty": "Easy",
                    "learning_objective": "Build initial verified code evidence starting with Functions.",
                    "prerequisites": [],
                    "has_sufficient_evidence": False,
                }

        # Select highest priority gap whose prerequisites are satisfied
        primary_gap = gaps[0]

        target_skill_name = primary_gap["name"]
        slug = primary_gap["slug"]
        ev_count = primary_gap["evidence_count"]
        status = primary_gap["status"]
        prereqs = primary_gap["prerequisites"]
        weak_prereqs = primary_gap["weak_prerequisites"]

        if ev_count == 0:
            difficulty = "Easy"
            reason = (
                f"Your Knowledge Mesh shows 0 evidence items for {target_skill_name}. "
                f"Ingesting code samples or practicing {target_skill_name} fundamentals will unlock your prerequisite path."
            )
            objective = f"Build initial verified code evidence for {target_skill_name}."
        elif status == "weak":
            difficulty = "Easy"
            reason = (
                f"Your Knowledge Mesh shows limited evidence ({ev_count} item) for {target_skill_name}. "
                f"Strengthening {target_skill_name} resolves a key prerequisite for advancing to higher-order algorithms."
            )
            objective = f"Reinforce {target_skill_name} patterns with targeted practice."
        else: # developing
            difficulty = "Medium"
            reason = (
                f"Your Knowledge Mesh shows developing evidence ({ev_count} items) for {target_skill_name}. "
                f"Advancing {target_skill_name} to Mastered status strengthens your foundational algorithmic core."
            )
            objective = f"Achieve mastery in {target_skill_name} with medium-complexity problems."

        if weak_prereqs:
            reason += f" Note: Prerequisite skill '{weak_prereqs[0]}' is also developing."

        return {
            "target_skill": target_skill_name,
            "slug": slug,
            "reason": reason,
            "evidence_count": ev_count,
            "recommended_difficulty": difficulty,
            "learning_objective": objective,
            "prerequisites": prereqs,
            "has_sufficient_evidence": True,
        }
