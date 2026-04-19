from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi import HTTPException

from src.api.limiter import limiter

from src.api.schemas import (
    ActaRewriteRequest,
    ActaRewriteResponse,
    AnalyzeRequest,
    AnalyzeResponse,
    ChatRequest,
    ChatResponse,
    ReviewRequest,
)
from src.config import get_settings
from src.parsers.document_parser import parse_document
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


@router.post("/api/upload")
async def upload_contract(file: UploadFile = File(...)) -> dict[str, str | int]:
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    filename = Path(file.filename or "uploaded.txt").name
    file_path = settings.upload_dir / filename
    file_path.write_bytes(await file.read())

    try:
        parsed = parse_document(str(file_path), filename)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"File parsing failed: {exc}") from exc

    full_text = parsed.raw_text.strip()
    if not full_text:
        raise HTTPException(status_code=400, detail="The uploaded contract did not contain readable text.")

    return {
        "filename": filename,
        "full_text": full_text,
        "char_count": len(full_text),
        "text_preview": full_text[:500],
    }


@router.post("/api/analyze", response_model=AnalyzeResponse)
@limiter.limit("5/minute")
async def analyze_contract(
    request: Request,
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
