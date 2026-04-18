from __future__ import annotations

from src.config import get_settings
from src.nlp.legal_nlp import extract_clauses
from src.pipeline.state import ContractReviewState


class ClauseExtractionAgent:
    def __call__(self, state: ContractReviewState) -> dict[str, object]:
        clauses = extract_clauses(state.raw_text, max_clauses=get_settings().analysis_max_clauses)
        return {"clauses": clauses}
