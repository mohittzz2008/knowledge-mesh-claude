"""AI Provider Abstraction Layer with Evidence Grounding."""

import logging
import os
import json
import httpx
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class CoachUnavailableError(ValueError):
    """No AI provider is configured. (ValueError subclass for backwards compatibility.)"""


class CoachProviderError(RuntimeError):
    """The configured AI provider failed or answered with an error."""


class BaseAIProvider(ABC):
    """Abstract Base Class for AI Coach Providers."""

    @abstractmethod
    def generate_response(self, context: dict[str, Any], user_message: str) -> dict[str, Any]:
        """Generate grounded response given database context and user prompt."""
        pass


class MockGroundedAIProvider(BaseAIProvider):
    """Evidence-grounded provider fallback when no external API key is set."""

    def generate_response(self, context: dict[str, Any], user_message: str) -> dict[str, Any]:
        msg_lower = user_message.lower()

        intent = context.get("intent", "GENERAL")
        ev_count = context.get("evidence_count", 0)
        artifacts = context.get("artifacts", [])
        nodes = context.get("nodes", [])
        nba = context.get("next_best_action", {})
        specific_art = context.get("specific_artifact")
        mistake_patterns = context.get("mistake_patterns", [])

        evidence_refs = []
        suggested_actions = []

        # Grounding references from context
        for art in artifacts[:3]:
            evidence_refs.append({
                "title": f"Code Artifact ({art['language']})",
                "platform": "GitHub",
                "repository": art["repository"],
                "file_path": art["file_path"],
                "source_url": art.get("source_url"),
            })

        # 1. Intent: CODE_LAB / Hint Request
        if intent == "CODE_LAB":
            ans = (
                f"### Code Lab Guidance & Hints\n\n"
                f"Here is your progressive hint for solving this problem:\n\n"
                f"1. **Identify Pattern**: Look for recursive branch conditions or tree traversal.\n"
                f"2. **Base Case**: Ensure base case returns an empty list or null node early.\n"
                f"3. **Optimization**: Avoid rebuilding intermediate lists repeatedly inside loops.\n\n"
                f"*Your recent Code Lab attempt was captured safely in the execution sandbox.*"
            )
            suggested_actions = [
                {"label": "Practice in Code Lab", "action_type": "code_lab", "target_path": "/code-lab"},
                {"label": "Compare Approach", "action_type": "code_lab", "target_path": "/code-lab"},
            ]
            return {
                "answer": ans,
                "confidence": min(1.0, 0.2 + (ev_count * 0.1)) if ev_count > 0 else 0.0,
                "context_used": {
                    "intent": intent,
                    "evidence_count": context.get("evidence_count", 0),
                    "connected_platforms": context.get("connected_platforms", []),
                },
                "evidence_references": evidence_refs,
                "suggested_actions": suggested_actions,
            }

        # 2. Intent: SKILL / EVIDENCE
        if intent in ["SKILL", "EVIDENCE"]:
            target_skill = nba.get("target_skill", "Recursion")
            reason = nba.get("reason", "Live PostgreSQL evidence tracking.")
            
            p_text = ""
            if mistake_patterns:
                p_text = f"\n\n**Detected Pattern Warning**: {mistake_patterns[0]['title']} — {mistake_patterns[0]['description']}"

            ans = (
                f"### Evidence-Grounded Skill Breakdown\n\n"
                f"Your Knowledge Mesh evaluates skill mastery using cross-platform telemetry:\n\n"
                f"• **GitHub**: {context.get('artifact_count', 0)} analyzed source artifacts\n"
                f"• **Connected Platforms**: {(', '.join(context.get('connected_platforms') or []) or 'none connected yet')}\n"
                f"• **Total Ingested Evidence**: {context.get('evidence_count', 0)} items in PostgreSQL\n\n"
                f"**Assessment**: {reason}{p_text}"
            )

            suggested_actions = [
                {"label": "Inspect Knowledge Mesh", "action_type": "mesh", "target_path": "/knowledge-mesh"},
                {"label": "View Learning Path", "action_type": "learning_path", "target_path": "/learning-path"},
            ]

            return {
                "answer": ans,
                "confidence": 0.92,
                "context_used": {
                    "intent": intent,
                    "target_skill": target_skill,
                    "evidence_count": context.get("evidence_count", 0),
                    "mistake_patterns_count": len(mistake_patterns),
                },
                "evidence_references": evidence_refs,
                "suggested_actions": suggested_actions,
            }

        # 3. Intent: RECOMMENDATION / LEARNING_PATH
        if intent in ["RECOMMENDATION", "LEARNING_PATH"]:
            target_skill = nba.get("target_skill", "Iteration")
            difficulty = nba.get("recommended_difficulty", "Easy")
            obj = nba.get("learning_objective", "Build initial evidence.")

            ans = (
                f"### Personalized Learning Path Recommendation\n\n"
                f"**Next Best Action**: Practice {target_skill} ({difficulty} Difficulty)\n\n"
                f"• **Objective**: {obj}\n"
                f"• **Prerequisite Rationale**: {nba.get('reason', 'Optimizes foundational prerequisite chain.')}\n\n"
                f"This recommendation is grounded in your cross-platform Knowledge Mesh assessments."
            )

            suggested_actions = [
                {"label": f"Practice {target_skill}", "action_type": "code_lab", "target_path": "/code-lab"},
                {"label": "View Full Learning Path", "action_type": "learning_path", "target_path": "/learning-path"},
            ]

            return {
                "answer": ans,
                "confidence": 0.96,
                "context_used": {
                    "intent": intent,
                    "target_skill": target_skill,
                    "recommended_difficulty": difficulty,
                },
                "evidence_references": evidence_refs,
                "suggested_actions": suggested_actions,
            }

        # 4. Low-Confidence or Zero Evidence Scenario
        has_real_evidence = context.get(
            "has_real_evidence",
            (context.get("evidence_count", 0) or 0) > 0 or (context.get("artifact_count", 0) or 0) > 0,
        )
        if not has_real_evidence:
            return {
                "answer": "I don't have enough verified evidence yet in your developer profile. Please run a sync on the Platforms page or complete a problem in Code Lab to build evidence!",
                "confidence": 0.50,
                "context_used": {"intent": intent, "has_real_evidence": False},
                "evidence_references": [],
                "suggested_actions": [
                    {"label": "Connect Platforms", "action_type": "platforms", "target_path": "/platforms"},
                    {"label": "Practice in Code Lab", "action_type": "code_lab", "target_path": "/code-lab"},
                ],
            }

        if len(msg_lower.strip()) < 4 or any(w in msg_lower for w in ["quantum", "biology", "cook", "fly"]):
            return {
                "answer": "I don't have enough verified evidence in your developer profile to answer that question confidently. Would you like to practice a Code Lab problem to build evidence?",
                "confidence": 0.30,
                "context_used": {"intent": "GENERAL", "low_confidence": True},
                "evidence_references": [],
                "suggested_actions": [
                    {"label": "Practice in Code Lab", "action_type": "code_lab", "target_path": "/code-lab"},
                    {"label": "Open Knowledge Mesh", "action_type": "mesh", "target_path": "/knowledge-mesh"},
                ],
            }

        # 5. Default Grounded Response
        target_skill = nba.get("target_skill", "Recursion")
        ans = (
            f"Hello! I am your Knowledge Mesh AI Coding Coach grounded in your PostgreSQL evidence pipeline.\n\n"
            f"Currently tracking:\n"
            f"• {context.get('evidence_count', 0)} Evidence Points across connected platforms ({(', '.join(context.get('connected_platforms') or []) or 'none connected yet')})\n"
            f"• {context.get('artifact_count', 0)} Analyzed Code Artifacts\n"
            f"• Current Focus Skill: '{target_skill}'\n\n"
            f"How can I assist your learning path today?"
        )

        suggested_actions = [
            {"label": "View Knowledge Mesh", "action_type": "mesh", "target_path": "/knowledge-mesh"},
            {"label": "View Learning Path", "action_type": "learning_path", "target_path": "/learning-path"},
            {"label": "Code Intelligence", "action_type": "code_intelligence", "target_path": "/code-intelligence"},
        ]

        return {
            "answer": ans,
            "confidence": 0.90,
            "context_used": {
                "intent": intent,
                "evidence_count": context.get("evidence_count", 0),
                "artifact_count": context.get("artifact_count", 0),
            },
            "evidence_references": evidence_refs,
            "suggested_actions": suggested_actions,
        }


class GeminiProvider(BaseAIProvider):
    """External Gemini Provider for AI Coach using httpx."""

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is missing.")
        self.base_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={self.api_key}"

    def generate_response(self, context: dict[str, Any], user_message: str) -> dict[str, Any]:
        intent = context.get("intent", "GENERAL")
        artifacts = context.get("artifacts", [])
        nba = context.get("next_best_action", {})
        evidence_count = context.get("evidence_count", 0)
        connected_platforms = context.get("connected_platforms", [])

        evidence_refs = []
        for art in artifacts[:3]:
            evidence_refs.append({
                "title": f"Code Artifact ({art.get('language', 'Unknown')})",
                "platform": art.get("platform", "GitHub"),
                "repository": art.get("repository"),
                "file_path": art.get("file_path"),
                "source_url": art.get("source_url"),
            })

        system_prompt = (
            "You are an expert AI Coding Coach with TWO operating modes.\n"
            "You must ALWAYS return your response as a valid JSON object matching the exact schema provided below. Do not wrap in markdown tags.\n\n"
            
            "== MODE 1: GROUNDED DEVELOPER COACH ==\n"
            "If the user asks about their profile, skill gaps, learning path, or evidence (e.g. 'Why am I weak at recursion?', 'What should I learn next?'), "
            "you MUST ground your response entirely in the following PostgreSQL evidence context. Never invent activity or claim evidence that is not listed here.\n"
            f"Context Intent: {intent}\n"
            f"Verified Evidence Count: {evidence_count}\n"
            f"Connected Platforms: {', '.join(connected_platforms) if connected_platforms else 'None'}\n"
            f"Next Best Action Skill: {nba.get('target_skill', 'None')}\n"
            f"Next Best Action Reason: {nba.get('reason', 'None')}\n\n"

            "== MODE 2: GENERAL CODING ASSISTANT ==\n"
            "If the user submits arbitrary code, algorithm problems, bug reports, or optimization requests (e.g., 'solve this problem', 'optimize this', 'fix my code'), "
            "you must act as an expert software engineer. Provide the corrected code, explanation, time/space complexity, edge cases, bugs, and compare approaches if applicable. "
            "Supported languages focus on Python, Java, and C, but you can support others as well. Do not claim code is correct unless your reasoning supports it.\n\n"
        )
        
        if artifacts:
            system_prompt += "Recent relevant source code files from the user's workspace/profile:\n"
            for art in artifacts[:3]:
                system_prompt += f"--- {art.get('file_path')} ---\n{art.get('code_content', '')}\n\n"

        system_prompt += (
            "== REQUIRED JSON OUTPUT SCHEMA ==\n"
            "{\n"
            '  "answer": "The main conversational response formatted in Markdown (do not put JSON here).",\n'
            '  "language": "python|java|c|...",\n'
            '  "corrected_code": "Code string if applicable, else null",\n'
            '  "approach": "Description of the chosen algorithmic approach, else null",\n'
            '  "complexity": {\n'
            '      "time": "O(...) string",\n'
            '      "space": "O(...) string"\n'
            '  },\n'
            '  "bugs": ["list of bugs found in original code, if any"],\n'
            '  "edge_cases": ["list of edge cases considered"],\n'
            '  "comparison": ["comparison of approaches if asked"],\n'
            '  "grounding": {\n'
            '      "used_profile": true/false,\n'
            f'      "evidence_count": {evidence_count},\n'
            '      "sources": ["list of platforms or specific evidence used"]\n'
            '  }\n'
            "}\n"
        )

        headers = {
            "Content-Type": "application/json"
        }
        
        combined_prompt = system_prompt + "\n\nUser Request:\n" + user_message
        
        payload = {
            "contents": [{
                "parts": [{"text": combined_prompt}]
            }],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.2
            }
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                res = client.post(self.base_url, headers=headers, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    
                    try:
                        json_str = data["candidates"][0]["content"]["parts"][0]["text"]
                        structured = json.loads(json_str)
                        if "complexity" not in structured or structured["complexity"] is None:
                            structured["complexity"] = {"time": "", "space": ""}
                        elif isinstance(structured["complexity"], dict):
                            if not structured["complexity"].get("time"):
                                structured["complexity"]["time"] = ""
                            if not structured["complexity"].get("space"):
                                structured["complexity"]["space"] = ""
                    except (KeyError, IndexError, json.JSONDecodeError):
                        structured = {"answer": "I failed to generate a valid JSON response."}
                    
                    return {
                        "answer": structured.get("answer", "No answer provided."),
                        "structured_data": {
                            "language": structured.get("language"),
                            "corrected_code": structured.get("corrected_code"),
                            "approach": structured.get("approach"),
                            "complexity": structured.get("complexity"),
                            "bugs": structured.get("bugs", []),
                            "edge_cases": structured.get("edge_cases", []),
                            "comparison": structured.get("comparison", []),
                            "grounding": structured.get("grounding", {}),
                        },
                        "confidence": 0.95,
                        "context_used": {
                            "intent": intent,
                            "evidence_count": evidence_count,
                            "target_skill": nba.get("target_skill"),
                        },
                        "evidence_references": evidence_refs,
                        "suggested_actions": [
                            {"label": "View Knowledge Mesh", "action_type": "mesh", "target_path": "/knowledge-mesh"},
                            {"label": "Practice in Code Lab", "action_type": "code_lab", "target_path": "/code-lab"}
                        ],
                    }
                else:
                    logger.error("Gemini API error %s: %s", res.status_code, res.text[:500])
                    raise CoachProviderError(f"Gemini API error {res.status_code}")
        except CoachProviderError:
            raise
        except Exception as e:
            logger.exception("Gemini provider failure")
            raise CoachProviderError(f"AI Provider failed: {e.__class__.__name__}") from e


def get_ai_provider() -> BaseAIProvider:
    """Factory returning active AI provider or raises error if not configured."""
    if os.getenv("GEMINI_API_KEY"):
        return GeminiProvider()
    
    # Do not silently fallback in production per rules.
    raise CoachUnavailableError("GEMINI_API_KEY is not configured in the environment. No silent fallbacks allowed.")
