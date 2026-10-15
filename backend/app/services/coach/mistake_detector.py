"""Mistake Pattern Detection Engine."""

from typing import Any
from sqlalchemy.orm import Session
from app.models.problem import CodeAttempt
from app.models.code_artifact import CodeArtifact, CodeAnalysis


class MistakeDetectorEngine:
    """Scans CodeAttempts & AST CodeAnalyses to detect recurring anti-patterns deterministically."""

    def detect_mistake_patterns(self, user_id: str, db: Session) -> list[dict[str, Any]]:
        patterns = []

        # 1. Inspect Code Lab Attempts
        attempts = (
            db.query(CodeAttempt)
            .filter(CodeAttempt.user_id == user_id)
            .order_by(CodeAttempt.created_at.desc())
            .limit(10)
            .all()
        )

        failed_attempts = [a for a in attempts if a.status != "completed"]
        syntax_errors = [a for a in attempts if getattr(a, "diagnostic_report", None) and "SyntaxError" in getattr(a, "diagnostic_report", "")]
        nested_loop_attempts = [a for a in attempts if getattr(a, "code_content", None) and getattr(a, "code_content", "").count("for ") >= 2]

        if len(failed_attempts) >= 2:
            patterns.append({
                "pattern_id": "frequent_test_failures",
                "title": "Frequent Test Case Failures",
                "severity": "HIGH",
                "description": f"Failed {len(failed_attempts)} recent Code Lab submission(s). Boundary edge cases may be unhandled.",
                "target_skill": "Error Handling",
                "evidence_count": len(failed_attempts),
            })

        if len(nested_loop_attempts) >= 1:
            patterns.append({
                "pattern_id": "nested_iteration_complexity",
                "title": "Nested Iteration Complexity",
                "severity": "MEDIUM",
                "description": "Detected multiple nested loops (O(N²)) in recent code attempts. Hashing or dictionaries could reduce complexity to O(N).",
                "target_skill": "Dictionaries",
                "evidence_count": len(nested_loop_attempts),
            })

        if len(syntax_errors) >= 1:
            patterns.append({
                "pattern_id": "syntax_errors",
                "title": "Syntax & Formatting Errors",
                "severity": "LOW",
                "description": "Encountered syntax errors during initial code execution. Verify indentation and colon placements.",
                "target_skill": "Functions",
                "evidence_count": len(syntax_errors),
            })

        # 2. Inspect AST Code Analyses
        analyses = (
            db.query(CodeAnalysis)
            .join(CodeArtifact, CodeAnalysis.code_artifact_id == CodeArtifact.id)
            .filter(CodeArtifact.user_id == user_id)
            .all()
        )

        recursive_analyses = [a for a in analyses if a.has_recursion]
        if recursive_analyses:
            patterns.append({
                "pattern_id": "recursion_base_case_vigilance",
                "title": "Recursion Base Case Check",
                "severity": "LOW",
                "description": f"Verified recursion in {len(recursive_analyses)} code file(s). Ensure base-case termination is explicitly declared.",
                "target_skill": "Recursion",
                "evidence_count": len(recursive_analyses),
            })

        return patterns
