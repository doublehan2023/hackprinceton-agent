from __future__ import annotations

from src.agents.clause_extraction import ClauseExtractionAgent
from src.agents.compliance_check import ComplianceCheckAgent
from src.agents.risk_identification import RiskIdentificationAgent
from src.agents.suggestion import SuggestionAgent
from src.parsers.document_parser import parse_text
from src.pipeline.state import ContractReviewState


def test_review_flow_handles_inline_text_with_headings() -> None:
    parsed = parse_text(
        "1. Confidentiality\n"
        "Confidential information must remain protected.\n\n"
        "2. Payment Terms\n"
        "Invoices are due within thirty days."
    )
    state = ContractReviewState(review_id="review-1", filename="inline.txt", raw_text=parsed.raw_text, sections=parsed.sections)

    state = state.model_copy(update=ClauseExtractionAgent()(state))
    state = state.model_copy(update=RiskIdentificationAgent()(state))
    state = state.model_copy(update=ComplianceCheckAgent()(state))
    state = state.model_copy(update=SuggestionAgent()(state))

    assert len(state.clauses) == 2
    assert state.summary.startswith("Reviewed 2 clauses.")
    assert {clause.section_title for clause in state.clauses} == {"1. Confidentiality", "2. Payment Terms"}
