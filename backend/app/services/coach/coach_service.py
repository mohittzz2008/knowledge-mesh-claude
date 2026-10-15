"""Coach Service Orchestrator."""

from typing import Any, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.coach import CoachConversation, CoachMessage
from app.services.coach.context_builder import CoachContextBuilder
from app.services.coach.provider_base import get_ai_provider


class CoachService:
    """Orchestrates AI Coach conversations, context grounding, and PostgreSQL persistence."""

    def process_user_message(
        self,
        user_id: str,
        message: str,
        db: Session,
        conversation_id: Optional[str] = None,
        code_artifact_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Process user query, ground in context, call provider, and persist in PostgreSQL."""
        # 0. Resolve the AI provider first: if none is configured, fail before any message is
        #    saved (otherwise the user is left with an orphaned message and no reply).
        provider = get_ai_provider()

        # 1. Get or create conversation
        if conversation_id:
            conversation = (
                db.query(CoachConversation)
                .filter(CoachConversation.id == conversation_id, CoachConversation.user_id == user_id)
                .first()
            )
        else:
            conversation = None

        if not conversation:
            conversation = CoachConversation(
                user_id=user_id,
                title=f"Coaching Session: {message[:40]}...",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(conversation)
            db.commit()
            db.refresh(conversation)

        # 2. Save user message
        user_msg_obj = CoachMessage(
            conversation_id=conversation.id,
            sender="user",
            content=message,
            created_at=datetime.now(timezone.utc),
        )
        db.add(user_msg_obj)
        db.commit()

        # 3. Build grounded context
        context_builder = CoachContextBuilder()
        context = context_builder.build_user_context(user_id, db, target_artifact_id=code_artifact_id, user_query=message)

        # 4. Generate AI response via provider
        res_data = provider.generate_response(context, message)

        # Merge structured_data into context_used for DB storage without schema migrations
        ctx_used = res_data.get("context_used") or {}
        structured = res_data.get("structured_data", {})
        if structured:
            ctx_used["structured_data"] = structured

        # 5. Save AI message in PostgreSQL
        ai_msg_obj = CoachMessage(
            conversation_id=conversation.id,
            sender="ai",
            content=res_data["answer"],
            context_used=ctx_used,
            evidence_references={"items": res_data.get("evidence_references", [])},
            suggested_actions={"items": res_data.get("suggested_actions", [])},
            created_at=datetime.now(timezone.utc),
        )
        db.add(ai_msg_obj)

        conversation.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(ai_msg_obj)

        return {
            "conversation_id": conversation.id,
            "message_id": ai_msg_obj.id,
            "answer": ai_msg_obj.content,
            "intent": context.get("intent", "GENERAL"),
            "confidence": res_data.get("confidence", 0.0),
            "context_used": ai_msg_obj.context_used,
            "evidence_references": res_data.get("evidence_references", []),
            "suggested_actions": res_data.get("suggested_actions", []),
            "detected_mistake_patterns": context.get("mistake_patterns", []),
            
            # Map structured data fields
            "language": structured.get("language"),
            "corrected_code": structured.get("corrected_code"),
            "approach": structured.get("approach"),
            "complexity": structured.get("complexity"),
            "bugs": structured.get("bugs", []),
            "edge_cases": structured.get("edge_cases", []),
            "comparison": structured.get("comparison", []),
            "grounding": structured.get("grounding", {}),
            
            "created_at": ai_msg_obj.created_at.isoformat(),
        }

    def get_user_conversations(self, user_id: str, db: Session) -> list[dict[str, Any]]:
        """List active coaching conversations for user."""
        convs = (
            db.query(CoachConversation)
            .filter(CoachConversation.user_id == user_id)
            .order_by(CoachConversation.updated_at.desc())
            .all()
        )
        return [
            {
                "id": c.id,
                "title": c.title,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
                "message_count": len(c.messages),
            }
            for c in convs
        ]

    def get_conversation_history(self, conversation_id: str, user_id: str, db: Session) -> dict[str, Any]:
        """Fetch full conversation message history."""
        conv = (
            db.query(CoachConversation)
            .filter(CoachConversation.id == conversation_id, CoachConversation.user_id == user_id)
            .first()
        )
        if not conv:
            return {"id": conversation_id, "messages": []}

        msgs = []
        for m in conv.messages:
            ev_refs = m.evidence_references.get("items", []) if m.evidence_references else []
            sug_acts = m.suggested_actions.get("items", []) if m.suggested_actions else []
            
            # Extract structured data if available
            ctx_used = m.context_used or {}
            structured = ctx_used.get("structured_data", {})

            msgs.append({
                "id": m.id,
                "sender": m.sender,
                "content": m.content,
                "context_used": ctx_used,
                "evidence_references": ev_refs,
                "suggested_actions": sug_acts,
                
                # Restore structured fields
                "language": structured.get("language"),
                "corrected_code": structured.get("corrected_code"),
                "approach": structured.get("approach"),
                "complexity": structured.get("complexity"),
                "bugs": structured.get("bugs", []),
                "edge_cases": structured.get("edge_cases", []),
                "comparison": structured.get("comparison", []),
                "grounding": structured.get("grounding", {}),

                "created_at": m.created_at.isoformat() if m.created_at else None,
            })

        return {
            "id": conv.id,
            "title": conv.title,
            "created_at": conv.created_at.isoformat() if conv.created_at else None,
            "messages": msgs,
        }

    def analyze_logic(self, user_id: str, request: Any, db: Session) -> dict[str, Any]:
        """Analyze entire submitted source code logic and return structured AST insights."""
        from app.services.analysis.parsers import get_structural_schema
        
        # 1. Run concrete static analysis
        structure = get_structural_schema(request.language, request.code)
        
        # 2. Ask AI to fill in subjective/algorithmic blanks based on structural ground truth
        provider = get_ai_provider()
        prompt = (
            f"You are a code intelligence engine. Analyze the following {request.language} program in its entirety.\n"
            f"Here is the exact structure extracted via concrete AST static analysis: {structure}\n\n"
            "You must trust this structural outline. Do not hallucinate additional classes or omit functions.\n\n"
            f"Code:\n```\n{request.code}\n```\n\n"
            "Return ONLY a raw JSON object matching these exact keys (do not wrap in markdown tags):\n"
            '{\n'
            '  "program_purpose": "string",\n'
            '  "functions": ["string"],\n'
            '  "classes": ["string"],\n'
            '  "methods": ["string"],\n'
            '  "control_flow": ["string"],\n'
            '  "loops": ["string"],\n'
            '  "conditionals": ["string"],\n'
            '  "recursion": ["string"],\n'
            '  "data_structures": ["string"],\n'
            '  "algorithm": "string",\n'
            '  "bugs": ["string"],\n'
            '  "suspicious_logic": ["string"],\n'
            '  "edge_cases": ["string"],\n'
            '  "time_complexity": "string",\n'
            '  "space_complexity": "string",\n'
            '  "optimization_opportunities": ["string"]\n'
            '}'
        )
        # We temporarily modify the provider behavior to enforce JSON response via response_format if it supports it
        # However, since OpenAIProvider currently intercepts generic payloads, we pass intent CODE
        context = {"intent": "CODE", "evidence_count": 0}
        
        # For full JSON reliability, we configure the provider payload
        # Note: Since provider_base OpenAIProvider checks for 'messages' internally, we rely on the system_prompt fallback
        # Wait, provider_base generates its own system prompt and JSON schema! 
        # But for analyze_logic, we'll just bypass the Coach message history and call OpenAI directly for raw tasks if needed.
        # Actually, let's just use a direct httpx call for backend raw intelligence tasks to ensure pure JSON enforcement
        # without the CoachMessage wrapping, or reuse OpenAIProvider if it handles raw prompts.
        # To avoid breaking OpenAIProvider's Coach structure, we'll do a direct internal call for intelligence:
        import os
        import httpx
        import json
        
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is missing.")
            
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.2
            }
        }
        
        try:
            with httpx.Client(timeout=30.0) as client:
                res = client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={api_key}", 
                    headers=headers, json=payload
                )
                if res.status_code == 200:
                    ans = res.json()["candidates"][0]["content"]["parts"][0]["text"]
                    parsed = json.loads(ans)
                    # Merge static structure with AI analysis
                    if isinstance(structure.get("functions"), list) and not parsed.get("functions"):
                        parsed["functions"] = structure.get("functions")
                    return parsed
                else:
                    return {"program_purpose": "Error connecting to AI Provider.", "error": res.text}
        except Exception as e:
            return {"program_purpose": f"Failed to parse logic: {str(e)}"}


    def compare_approach(self, user_id: str, request: Any, db: Session) -> dict[str, Any]:
        """Compare two coding approaches for correctness, complexity, and maintainability."""
        prompt = (
            f"Compare these two {request.language} approaches for the problem: {request.problem}\n\n"
            f"Approach A:\n```\n{request.approach_a}\n```\n\n"
            f"Approach B:\n```\n{request.approach_b}\n```\n\n"
            "Return ONLY a raw JSON object matching exactly these keys (do not wrap in markdown tags):\n"
            '{\n'
            '  "correctness": "string",\n'
            '  "time_complexity": "string (comparing both)",\n'
            '  "space_complexity": "string (comparing both)",\n'
            '  "readability": "string",\n'
            '  "maintainability": "string",\n'
            '  "edge_cases": "string",\n'
            '  "recommended_approach": "string",\n'
            '  "reason": "string"\n'
            '}'
        )
        import os
        import httpx
        import json
        
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is missing.")
            
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.2
            }
        }
        
        try:
            with httpx.Client(timeout=30.0) as client:
                res = client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={api_key}", 
                    headers=headers, json=payload
                )
                if res.status_code == 200:
                    ans = res.json()["candidates"][0]["content"]["parts"][0]["text"]
                    return json.loads(ans)
                else:
                    return {"recommended_approach": "Error", "reason": res.text}
        except Exception as e:
            return {"recommended_approach": "Error", "reason": str(e)}
