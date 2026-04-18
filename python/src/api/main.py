from __future__ import annotations

import uuid
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.config import get_settings
from src.parsers.document_parser import extract_text
from src.pipeline.graph import create_review_pipeline
from src.pipeline.state import ContractReviewState, RiskLevel


class AnalyzeRequest(BaseModel):
    title: str = Field(min_length=1)
    filename: str = "inline.txt"
    text: str = Field(min_length=1)


class ReviewRequest(BaseModel):
    text: str = Field(min_length=1)
    title: str = "Contract Review"
    with_human_review: bool = False


class AssessmentPayload(BaseModel):
    clause_type: str
    raw_text: str
    risk_level: str
    deviation_summary: str
    suggested_action: str
    confidence: float


class RedlinePayload(BaseModel):
    proposed_text: str


class ClausePayload(BaseModel):
    assessment: AssessmentPayload
    redline: RedlinePayload | None = None


class AnalyzeResponse(BaseModel):
    summary: str
    clauses: list[ClausePayload]
    missing_clause_types: list[str] = Field(default_factory=list)


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


def _build_state(payload: AnalyzeRequest) -> ContractReviewState:
    return ContractReviewState(
        review_id=str(uuid.uuid4()),
        filename=payload.filename,
        raw_text=payload.text,
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
                    RedlinePayload(proposed_text=redline.proposed_text)
                    if redline is not None and finding.risk_level is not RiskLevel.GREEN
                    else None
                ),
            )
        )

    return AnalyzeResponse(
        summary=result.summary,
        clauses=clauses,
        missing_clause_types=result.missing_clause_types,
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
            raw_text = extract_text(str(file_path), filename).strip()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"File parsing failed: {exc}") from exc

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


if __name__ == "__main__":
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=False)
