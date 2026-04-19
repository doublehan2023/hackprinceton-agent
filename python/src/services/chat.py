from __future__ import annotations

try:
    from langchain_core.prompts import ChatPromptTemplate
except ImportError:  # pragma: no cover - optional dependency in local test env
    ChatPromptTemplate = None  # type: ignore[assignment,misc]

from src.api.schemas import ChatResponse
from src.llm import get_llm_client, truncate_text

_MAX_CONTEXT_CHARS = 12_000

_SYSTEM = (
    "You are a precise legal contract analysis assistant for clinical trial agreements. "
    "Answer the user's question using the supplied contract context when available. "
    "If the context is insufficient, say so clearly instead of inventing details. "
    "Keep answers concise, practical, and focused on the contract text."
)

_HUMAN = "Question:\n{question}\n\nContract context:\n{context}"

CHAT_PROMPT: object = (
    ChatPromptTemplate.from_messages([("system", _SYSTEM), ("human", _HUMAN)])
    if ChatPromptTemplate is not None
    else None
)


def _prepare_context(context: str) -> str:
    stripped = context.strip()
    if not stripped:
        return "[No contract context provided]"
    return truncate_text(stripped, _MAX_CONTEXT_CHARS)


def _fallback_answer(question: str, context: str) -> str:
    if context.strip():
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


def answer_chat(question: str, context: str, *, llm: object | None = None) -> ChatResponse:
    client = get_llm_client()[0] if llm is None else llm
    if client is None or CHAT_PROMPT is None:
        return ChatResponse(answer=_fallback_answer(question, context))

    try:
        chain = CHAT_PROMPT | client.with_structured_output(ChatResponse)
        result = chain.invoke({"question": question.strip(), "context": _prepare_context(context)})
        if isinstance(result, ChatResponse) and result.answer:
            return result
    except Exception:
        pass

    return ChatResponse(answer=_fallback_answer(question, context))
