import asyncio
from datetime import datetime, UTC

from backend.repository import create_clause, create_negotiation, create_redline, create_version, get_next_version_number
from backend.schemas import AnalyzeRequest, AnalyzeResponse, ClauseResult, RiskLevel
from backend.services.agents import analyze_clause, classify_document, generate_redline


class AnalysisOrchestrator:
    async def run(self, payload: AnalyzeRequest) -> AnalyzeResponse:
        negotiation_id = payload.negotiation_id or create_negotiation(
            payload.title,
            payload.sponsor,
            payload.site,
            payload.pen_holder,
        )
        version_number = get_next_version_number(negotiation_id)
        version_id = create_version(
            negotiation_id=negotiation_id,
            version_number=version_number,
            uploaded_by=payload.uploaded_by,
            filename=payload.filename,
            raw_text=payload.text,
        )

        clause_map = classify_document(payload.text)
        assessments = await asyncio.gather(
            *(asyncio.to_thread(analyze_clause, clause) for clause in clause_map.clauses)
        )

        clause_results: list[ClauseResult] = []
        for classified_clause, assessment in zip(clause_map.clauses, assessments, strict=False):
            clause_id = create_clause(
                version_id=version_id,
                assessment=assessment,
                classification_confidence=classified_clause.classification_confidence,
            )
            redline = generate_redline(assessment)
            if redline is not None:
                create_redline(clause_id, redline)
            clause_results.append(ClauseResult(id=clause_id, assessment=assessment, redline=redline))

        red_count = sum(1 for clause in clause_results if clause.assessment.risk_level == RiskLevel.red)
        yellow_count = sum(1 for clause in clause_results if clause.assessment.risk_level == RiskLevel.yellow)
        review_count = sum(1 for clause in clause_results if clause.assessment.human_review_required)

        summary = (
            f"Processed {len(clause_results)} clauses. "
            f"Detected {red_count} red, {yellow_count} yellow, and {review_count} clauses needing human review."
        )

        return AnalyzeResponse(
            negotiation_id=negotiation_id,
            version_id=version_id,
            version_number=version_number,
            summary=summary,
            missing_clause_types=clause_map.missing_clause_types,
            clauses=clause_results,
            generated_at=datetime.now(UTC),
        )
