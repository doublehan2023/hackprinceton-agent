from __future__ import annotations

from src.pipeline.state import ContractReviewState, RiskFinding
from src.rules.engine import evaluate_clause_risk


class RiskIdentificationAgent:
    def __call__(self, state: ContractReviewState) -> dict[str, object]:
        findings: list[RiskFinding] = [evaluate_clause_risk(clause) for clause in state.clauses]
        needs_human_review = any(finding.needs_human_review for finding in findings)
        return {
            "risk_findings": findings,
            "needs_human_review": needs_human_review,
        }
