from __future__ import annotations

import re
import uuid
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.config import get_llm, get_settings
from src.parsers.document_parser import parse_document, parse_text
from src.pipeline.graph import create_review_pipeline
from src.pipeline.state import ContractReviewState, RiskLevel

try:
    from langchain_core.messages import HumanMessage, SystemMessage
except ImportError:  # pragma: no cover - optional dependency in local test env
    HumanMessage = None
    SystemMessage = None


class AnalyzeRequest(BaseModel):
    title: str = Field(min_length=1)
    filename: str = "inline.txt"
    text: str = Field(min_length=1)


class ReviewRequest(BaseModel):
    text: str = Field(min_length=1)
    title: str = "Contract Review"
    with_human_review: bool = False


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    context: str = ""


class ChatResponse(BaseModel):
    answer: str


class AssessmentPayload(BaseModel):
    clause_type: str
    raw_text: str
    risk_level: str
    deviation_summary: str
    suggested_action: str
    confidence: float


class RedlinePayload(BaseModel):
    proposed_text: str
    original_text: str = ""
    suggested_text: str = ""
    reason: str = ""
    priority: str = "medium"


class SuggestionPayload(BaseModel):
    clause_id: str
    clause_type: str
    original_text: str = ""
    suggested_text: str = ""
    reason: str = ""
    priority: str = "medium"
    confidence: float


class ClausePayload(BaseModel):
    assessment: AssessmentPayload
    redline: RedlinePayload | None = None
    model_used: str | None = None


class AnalyzeResponse(BaseModel):
    summary: str
    clauses: list[ClausePayload]
    suggestions: list[SuggestionPayload] = Field(default_factory=list)
    missing_clause_types: list[str] = Field(default_factory=list)
    extraction_model: str | None = None
    version_diff: str = ""
    risk_score: int = 0


settings = get_settings()
pipeline = create_review_pipeline()

app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/health")
async def versioned_health() -> dict[str, str]:
    return {"status": "ok"}


def _truncate_context(context: str, max_chars: int = 12000) -> str:
    context = context.strip()
    if len(context) <= max_chars:
        return context
    return context[:max_chars].rstrip() + "\n\n[TRUNCATED]"


def _fallback_chat_answer(question: str, context: str) -> str:
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


def _build_chat_messages(question: str, context: str) -> list[object]:
    system_prompt = (
        "You are a precise legal contract analysis assistant for clinical trial agreements. "
        "Answer the user's question using the supplied contract context when available. "
        "If the context is insufficient, say so clearly instead of inventing details. "
        "Keep answers concise, practical, and focused on the contract text."
    )
    user_prompt = (
        f"Question:\n{question.strip()}\n\n"
        f"Contract context:\n{_truncate_context(context) if context.strip() else '[No contract context provided]'}"
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


def _coerce_chat_content(content: object) -> str:
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

    # K2 Think responses may include hidden reasoning in <think> blocks, and
    # some payloads may only expose the trailing closing marker.
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
    if "</think>" in text.lower():
        parts = re.split(r"</think>", text, flags=re.IGNORECASE, maxsplit=1)
        text = parts[-1].strip()
    return text


def _build_state(payload: AnalyzeRequest) -> ContractReviewState:
    parsed = parse_text(payload.text)
    return ContractReviewState(
        review_id=str(uuid.uuid4()),
        filename=payload.filename,
        raw_text=parsed.raw_text,
        sections=parsed.sections,
    )


def _normalize_response(result: ContractReviewState) -> AnalyzeResponse:
    suggestion_map = {suggestion.clause_id: suggestion for suggestion in result.suggestions}
    clauses: list[ClausePayload] = []

    for finding in result.risk_findings:
        redline = suggestion_map.get(finding.clause_id)
        clauses.append(
            ClausePayload(
                assessment=AssessmentPayload(
                    clause_type=finding.clause_type.value,
                    raw_text=finding.clause_text,
                    risk_level=finding.risk_level.value,
                    deviation_summary=finding.deviation_summary,
                    suggested_action=finding.suggested_action,
                    confidence=finding.confidence,
                ),
                redline=(
                    RedlinePayload(
                        proposed_text=redline.proposed_text or redline.suggested_text,
                        original_text=redline.original_text,
                        suggested_text=redline.suggested_text or redline.proposed_text,
                        reason=redline.reason or redline.rationale,
                        priority=redline.priority,
                    )
                    if redline is not None and finding.risk_level is not RiskLevel.GREEN
                    else None
                ),
                model_used=result.extraction_model,
            )
        )

    return AnalyzeResponse(
        summary=result.summary,
        clauses=clauses,
        suggestions=[
            SuggestionPayload(
                clause_id=suggestion.clause_id,
                clause_type=suggestion.clause_type.value,
                original_text=suggestion.original_text,
                suggested_text=suggestion.suggested_text or suggestion.proposed_text,
                reason=suggestion.reason or suggestion.rationale,
                priority=suggestion.priority,
                confidence=suggestion.confidence,
            )
            for suggestion in result.suggestions
        ],
        missing_clause_types=result.missing_clause_types,
        extraction_model=result.extraction_model,
        version_diff=result.version_diff,
        risk_score=result.risk_score,
    )


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze_contract(
    title: str = Form(...),
    text: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
) -> AnalyzeResponse:
    if not text and not file:
        raise HTTPException(status_code=400, detail="Provide raw text or an uploaded contract file.")

    filename = "inline.txt"
    raw_text = (text or "").strip()

    if file is not None:
        settings.upload_dir.mkdir(parents=True, exist_ok=True)
        filename = file.filename or "uploaded.txt"
        file_path = settings.upload_dir / Path(filename).name
        file_path.write_bytes(await file.read())
        try:
            raw_text = parse_document(str(file_path), filename).raw_text
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"File parsing failed: {exc}") from exc

    raw_text = raw_text.strip()
    if not raw_text:
        raise HTTPException(status_code=400, detail="The uploaded contract did not contain readable text.")

    state = _build_state(AnalyzeRequest(title=title, filename=filename, text=raw_text))
    result = await pipeline.ainvoke(state)
    return _normalize_response(ContractReviewState.model_validate(result))


@app.post("/api/v1/review", response_model=AnalyzeResponse)
async def create_review(request: ReviewRequest) -> AnalyzeResponse:
    state = _build_state(
        AnalyzeRequest(
            title=request.title,
            filename="inline.txt",
            text=request.text.strip(),
        )
    )
    result = await pipeline.ainvoke(state)
    return _normalize_response(ContractReviewState.model_validate(result))


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    llm = get_llm()
    if llm is None:
        return ChatResponse(answer=_fallback_chat_answer(request.question, request.context))

    try:
        response = llm.invoke(_build_chat_messages(request.question, request.context))
        answer = _coerce_chat_content(getattr(response, "content", response))
    except Exception:
        answer = _fallback_chat_answer(request.question, request.context)

    if not answer:
        answer = _fallback_chat_answer(request.question, request.context)

    return ChatResponse(answer=answer)


if __name__ == "__main__":
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=False)
