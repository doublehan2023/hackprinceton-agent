from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from src.api.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    AssessmentPayload,
    ClausePayload,
    RedlinePayload,
    SuggestionPayload,
)
from src.config import get_settings
from src.parsers.document_parser import parse_document, parse_text
from src.pipeline.graph import create_review_pipeline
from src.pipeline.state import ContractReviewState, RiskLevel


pipeline = create_review_pipeline()


def build_state(payload: AnalyzeRequest) -> ContractReviewState:
    parsed = parse_text(payload.text)
    return ContractReviewState(
        review_id=str(uuid.uuid4()),
        filename=payload.filename,
        raw_text=parsed.raw_text,
        sections=parsed.sections,
    )


def normalize_review_response(result: ContractReviewState) -> AnalyzeResponse:
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


async def run_inline_review(request: AnalyzeRequest) -> AnalyzeResponse:
    state = build_state(request)
    result = await pipeline.ainvoke(state)
    return normalize_review_response(ContractReviewState.model_validate(result))


async def run_uploaded_contract_review(
    *,
    title: str,
    text: str | None = None,
    file: UploadFile | None = None,
) -> AnalyzeResponse:
    if not text and not file:
        raise HTTPException(status_code=400, detail="Provide raw text or an uploaded contract file.")

    settings = get_settings()
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

    return await run_inline_review(AnalyzeRequest(title=title, filename=filename, text=raw_text))
