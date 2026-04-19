from __future__ import annotations

import re

from src.api.schemas import ChatResponse
from src.config import get_llm

try:
    from langchain_core.messages import HumanMessage, SystemMessage
except ImportError:  # pragma: no cover - optional dependency in local test env
    HumanMessage = None
    SystemMessage = None


def truncate_context(context: str, max_chars: int = 12000) -> str:
    context = context.strip()
    if len(context) <= max_chars:
        return context
    return context[:max_chars].rstrip() + "\n\n[TRUNCATED]"


def fallback_chat_answer(question: str, context: str) -> str:
    cleaned_context = context.strip()
    if cleaned_context:
        return (
            "I could not reach the configured language model, so here is a context-grounded fallback.\n\n"
            f"Question: {question.strip()}\n\n"
            "The uploaded contract context is available, but advanced Q&A is currently offline. "
            "Please check that `OPENAI_API_KEY` is set for the Python service and try again."
        )
    return (
        "I could not reach the configured language model, and no contract context was provided. "
        "Please upload or analyze a contract first, then ask your question again."
    )


def build_chat_messages(question: str, context: str) -> list[object]:
    system_prompt = (
        "You are a precise legal contract analysis assistant for clinical trial agreements. "
        "Answer the user's question using the supplied contract context when available. "
        "If the context is insufficient, say so clearly instead of inventing details. "
        "Keep answers concise, practical, and focused on the contract text."
    )
    user_prompt = (
        f"Question:\n{question.strip()}\n\n"
        f"Contract context:\n{truncate_context(context) if context.strip() else '[No contract context provided]'}"
    )

    if HumanMessage is not None and SystemMessage is not None:
        return [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def coerce_chat_content(content: object) -> str:
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict):
                parts.append(str(part.get("text", "")))
            else:
                text = getattr(part, "text", None)
                parts.append(str(text if text is not None else part))
        return "".join(parts).strip()
    if isinstance(content, str):
        text = content.strip()
    else:
        text = str(content).strip()

    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
    if "</think>" in text.lower():
        parts = re.split(r"</think>", text, flags=re.IGNORECASE, maxsplit=1)
        text = parts[-1].strip()
    return text


def answer_chat(question: str, context: str, *, llm: object | None = None) -> ChatResponse:
    client = get_llm() if llm is None else llm
    if client is None:
        return ChatResponse(answer=fallback_chat_answer(question, context))

    try:
        response = client.invoke(build_chat_messages(question, context))
        answer = coerce_chat_content(getattr(response, "content", response))
    except Exception:
        answer = fallback_chat_answer(question, context)

    if not answer:
        answer = fallback_chat_answer(question, context)

    return ChatResponse(answer=answer)
