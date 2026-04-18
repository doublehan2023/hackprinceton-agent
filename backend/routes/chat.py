from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from backend.services.llm import call_gemini

router = APIRouter()


# =========================
# REQUEST MODEL
# =========================
class ChatRequest(BaseModel):
    question: str
    context: str  # full contract or selected clause text
    gemini_key: Optional[str] = None


# =========================
# CHAT ENDPOINT
# =========================
@router.post("/chat")
def chat_with_contract(req: ChatRequest):

    if not req.question or not req.context:
        raise HTTPException(
            status_code=400,
            detail="Both question and context are required"
        )

    prompt = f"""
You are ACTA AI, a senior clinical trial legal expert.

Your job is to help users understand and negotiate clinical trial agreements.

You MUST:
- Give legally accurate explanations
- Identify risks clearly
- Suggest improvements when relevant
- Be concise but precise
- If unsure, clearly say so

----------------------------
CONTRACT CONTEXT:
----------------------------
{req.context}

----------------------------
USER QUESTION:
----------------------------
{req.question}

----------------------------
OUTPUT FORMAT:
- Direct answer first
- Then risk explanation (if any)
- Then negotiation suggestion (if relevant)
"""

    try:
        # Use frontend-provided key OR fallback (if you later add env key)
        api_key = req.gemini_key or ""

        response = call_gemini(api_key, prompt)

        if not response:
            return {
                "answer": "⚠️ AI could not generate a response. Please try again."
            }

        return {
            "answer": response,
            "status": "success"
        }

    except Exception as e:
        return {
            "answer": "❌ Error generating response",
            "error": str(e)
        }