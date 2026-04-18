from __future__ import annotations

from src.pipeline.state import ComplianceFinding, ContractReviewState
from src.rules.engine import find_missing_clause_types


class ComplianceCheckAgent:
    def __call__(self, state: ContractReviewState) -> dict[str, object]:
        missing_clause_types = find_missing_clause_types(state.clauses)
        findings: list[ComplianceFinding] = []
        for clause_type in missing_clause_types:
            findings.append(
                ComplianceFinding(
                    clause_type=clause_type,
                    status="missing",
                    detail=f"Missing expected CTA section: {clause_type}.",
                )
            )

        return {
            "compliance_findings": findings,
            "missing_clause_types": missing_clause_types,
            "needs_human_review": state.needs_human_review or bool(missing_clause_types),
        }
