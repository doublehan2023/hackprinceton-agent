from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile

from src.api.schemas import (
    ActaRewriteRequest,
    ActaRewriteResponse,
    AnalyzeRequest,
    AnalyzeResponse,
    ChatRequest,
    ChatResponse,
    ReviewRequest,
)
from src.services.chat import answer_chat
from src.services.review import run_inline_review, run_uploaded_contract_review
from src.services.rewrite import rewrite_to_acta


router = APIRouter()


@router.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/v1/health")
async def versioned_health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze_contract(
    title: str = Form(...),
    text: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
) -> AnalyzeResponse:
    return await run_uploaded_contract_review(title=title, text=text, file=file)


@router.post("/api/v1/review", response_model=AnalyzeResponse)
async def create_review(request: ReviewRequest) -> AnalyzeResponse:
    return await run_inline_review(
        AnalyzeRequest(
            title=request.title,
            filename="inline.txt",
            text=request.text.strip(),
        )
    )


@router.post("/api/acta-rewrite", response_model=ActaRewriteResponse)
async def acta_rewrite(request: ActaRewriteRequest) -> ActaRewriteResponse:
    return rewrite_to_acta(request)


@router.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    return answer_chat(request.question, request.context)
