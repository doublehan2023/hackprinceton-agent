from __future__ import annotations

from collections import Counter

from src.pipeline.state import ContractReviewState, RiskLevel, Suggestion
from src.rules.engine import build_suggestion_for_finding


class SuggestionAgent:
    def __call__(self, state: ContractReviewState) -> dict[str, object]:
        suggestions: list[Suggestion] = []
        for finding in state.risk_findings:
            suggestion = build_suggestion_for_finding(finding)
            if suggestion is not None:
                suggestions.append(suggestion)

        counts = Counter(finding.risk_level for finding in state.risk_findings)
        summary = (
            f"Reviewed {len(state.risk_findings)} clauses. "
            f"Detected {counts[RiskLevel.RED]} critical, {counts[RiskLevel.YELLOW]} minor, "
            f"and {counts[RiskLevel.GREEN]} aligned clauses."
        )

        return {
            "suggestions": suggestions,
            "summary": summary,
        }
