"""Deterministic Question Intent Router for AI Coach."""

import re
from typing import Literal

from app.services.platform import PlatformRegistry

IntentType = Literal[
    "SKILL",
    "EVIDENCE",
    "CODE",
    "RECOMMENDATION",
    "LEARNING_PATH",
    "PLATFORM",
    "PROGRESS",
    "CODE_LAB",
    "GENERAL"
]


class QuestionRouter:
    """Classifies user chat queries into deterministic intent categories without LLM latency."""

    @staticmethod
    def classify_intent(query: str) -> IntentType:
        q = query.lower().strip()

        # 1. EVIDENCE
        if any(kw in q for kw in ["evidence", "proof", "show evidence", "where did", "sources", "artifacts"]):
            return "EVIDENCE"

        # 2. CODE_LAB & HINTS
        if any(kw in q for kw in ["hint", "code lab", "test case", "test failure", "run code", "optimize my code"]):
            return "CODE_LAB"

        # 3. CODE & COMPLEXITY
        if any(kw in q for kw in ["complexity", "time complexity", "space complexity", "slow", "nested loop", "ast analysis"]):
            return "CODE"

        # 4. RECOMMENDATION
        if any(kw in q for kw in ["recommend", "practice next", "what to practice", "why recommend", "problem matcher"]):
            return "RECOMMENDATION"

        # 5. LEARNING_PATH
        if any(kw in q for kw in ["learning path", "roadmap", "learn next", "future goal", "prerequisite"]):
            return "LEARNING_PATH"

        # 6. PLATFORM
        platform_keywords = [n.lower() for n in PlatformRegistry.platform_names()] + ["gfg"]
        if any(kw in q for kw in platform_keywords + ["platform", "connected", "sync"]):
            return "PLATFORM"

        # 7. PROGRESS
        if any(kw in q for kw in ["improved", "better at", "progress", "change", "history"]):
            return "PROGRESS"

        # 8. SKILL & GAPS
        if any(kw in q for kw in ["weak", "strong", "skill", "mastery", "recursion", "trees", "dfs", "gap", "assessment"]):
            return "SKILL"

        return "GENERAL"
