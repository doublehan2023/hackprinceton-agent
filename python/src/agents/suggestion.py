from __future__ import annotations

import difflib
import json
import logging
import re
from collections import Counter

from src.config import get_llm
from src.pipeline.state import (
    ClauseType,
    ComplianceFinding,
    ContractReviewState,
    RiskFinding,
    RiskLevel,
    Suggestion,
)
from src.rules.engine import PLAYBOOK, build_suggestion_for_finding

logger = logging.getLogger(__name__)

try:
    from langchain_core.messages import HumanMessage, SystemMessage
except ImportError:  # pragma: no cover - optional dependency in local test env
    HumanMessage = None
    SystemMessage = None


SYSTEM_PROMPT = """You are a senior contract redlining advisor for clinical trial agreements.

Generate concrete clause revision suggestions based on the supplied risk and compliance findings.
Return valid JSON only using this schema:
{
  "suggestions": [
    {
      "clause_id": "clause-1",
      "original_text": "original clause text",
      "suggested_text": "revised clause text",
      "reason": "why this revision is recommended",
      "priority": "high|medium|low"
    }
  ]
}

Rules:
- Return JSON only, with no markdown fences.
- Keep the legal drafting style precise and negotiation-ready.
- Prioritize material risk and compliance concerns first.
- Use the original clause text as the basis for the rewrite instead of replacing it with generic advice.
"""

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
RISK_TO_PRIORITY = {
    RiskLevel.RED: "high",
    RiskLevel.YELLOW: "medium",
    RiskLevel.GREEN: "low",
}


class SuggestionAgent:
    def __init__(self) -> None:
        self.llm = None

    def _ensure_llm(self) -> None:
        if self.llm is None:
            self.llm = get_llm()

    def __call__(self, state: ContractReviewState) -> dict[str, object]:
        logger.info("Starting suggestion generation for review_id=%s", state.review_id)

        if not state.risk_findings and not state.compliance_findings:
            summary = state.risk_summary or "Reviewed 0 clauses. No redlines were required."
            return {
                "suggestions": [],
                "version_diff": "No changes required.",
                "summary": summary,
            }

        try:
            self._ensure_llm()
            suggestions = self._generate_suggestions(
                state.risk_findings,
                state.compliance_findings,
            )
        except Exception as exc:  # pragma: no cover - exercised by integration behavior
            logger.warning("Suggestion LLM generation failed, using fallback: %s", exc)
            suggestions = self._fallback_suggestions(
                state.risk_findings,
                state.compliance_findings,
            )

        suggestions.extend(self._missing_clause_suggestions(state.compliance_findings))
        suggestions = self._dedupe_and_sort_suggestions(suggestions)

        version_diff = self._generate_version_diff(suggestions)
        summary = self._build_summary(state)
        needs_human_review = state.needs_human_review or any(
            suggestion.priority == "high" for suggestion in suggestions
        )

        return {
            "suggestions": suggestions,
            "version_diff": version_diff,
            "summary": summary,
            "needs_human_review": needs_human_review,
        }

    def _generate_suggestions(
        self,
        risk_findings: list[RiskFinding],
        compliance_findings: list[ComplianceFinding],
    ) -> list[Suggestion]:
        if self.llm is None:
            return self._fallback_suggestions(risk_findings, compliance_findings)

        context_parts = self._build_context_parts(risk_findings, compliance_findings)
        if not context_parts:
            return []

        user_prompt = "Generate clause revision suggestions for these findings:\n\n" + "\n\n---\n\n".join(context_parts)

        if HumanMessage is not None and SystemMessage is not None:
            messages = [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=user_prompt),
            ]
        else:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]

        response = self.llm.invoke(messages)
        content = self._clean_response_content(getattr(response, "content", response))
        payload = json.loads(content)

        suggestions: list[Suggestion] = []
        findings_by_id = {finding.clause_id: finding for finding in risk_findings}
        for item in payload.get("suggestions", []):
            clause_id = str(item.get("clause_id", "")).strip()
            if not clause_id:
                continue

            original_text = str(item.get("original_text", "")).strip()
            suggested_text = str(item.get("suggested_text", "")).strip()
            reason = str(item.get("reason", "")).strip()
            priority = self._normalize_priority(item.get("priority"))
            risk_finding = findings_by_id.get(clause_id)
            clause_type = risk_finding.clause_type if risk_finding is not None else ClauseType.GENERAL

            if not suggested_text:
                continue

            suggestions.append(
                Suggestion(
                    clause_id=clause_id,
                    clause_type=clause_type,
                    proposed_text=suggested_text,
                    rationale=reason,
                    confidence=min(0.95, risk_finding.confidence if risk_finding is not None else 0.75),
                    original_text=original_text,
                    suggested_text=suggested_text,
                    reason=reason,
                    priority=priority,
                )
            )

        if suggestions:
            return suggestions
        return self._fallback_suggestions(risk_findings, compliance_findings)

    def _build_context_parts(
        self,
        risk_findings: list[RiskFinding],
        compliance_findings: list[ComplianceFinding],
    ) -> list[str]:
        context_parts: list[str] = []

        for finding in risk_findings:
            if finding.risk_level is RiskLevel.GREEN:
                continue
            context_parts.append(
                "\n".join(
                    [
                        f"[Risk: {finding.risk_level.value}]",
                        f"Clause ID: {finding.clause_id}",
                        f"Clause type: {finding.clause_type.value}",
                        f"Original text: {finding.clause_text}",
                        f"Deviation summary: {finding.deviation_summary}",
                        f"Suggested action: {finding.suggested_action}",
                        f"Rationale: {finding.rationale or finding.deviation_summary}",
                    ]
                )
            )

        for finding in compliance_findings:
            if finding.status.lower() == "compliant":
                continue
            context_parts.append(
                "\n".join(
                    [
                        f"[Compliance: {finding.status}]",
                        f"Clause type: {finding.clause_type}",
                        f"Detail: {finding.detail}",
                    ]
                )
            )

        return context_parts

    def _fallback_suggestions(
        self,
        risk_findings: list[RiskFinding],
        compliance_findings: list[ComplianceFinding],
    ) -> list[Suggestion]:
        suggestions: list[Suggestion] = []
        seen_clause_ids: set[str] = set()

        for finding in risk_findings:
            if finding.risk_level is RiskLevel.GREEN or finding.needs_human_review:
                continue

            baseline = build_suggestion_for_finding(finding)
            suggested_text = baseline.proposed_text if baseline is not None else str(
                PLAYBOOK[finding.clause_type]["standard_text"]
            )
            reason = finding.rationale or finding.deviation_summary
            priority = RISK_TO_PRIORITY[finding.risk_level]

            suggestions.append(
                Suggestion(
                    clause_id=finding.clause_id,
                    clause_type=finding.clause_type,
                    proposed_text=suggested_text,
                    rationale=reason,
                    confidence=max(finding.confidence, 0.65),
                    original_text=finding.clause_text,
                    suggested_text=suggested_text,
                    reason=reason,
                    priority=priority,
                )
            )
            seen_clause_ids.add(finding.clause_id)

        for finding in compliance_findings:
            if finding.status.lower() == "compliant":
                continue

            synthetic_id = f"missing:{finding.clause_type.lower().replace(' ', '_')}"
            if synthetic_id in seen_clause_ids:
                continue

            suggestions.append(
                Suggestion(
                    clause_id=synthetic_id,
                    clause_type=ClauseType.GENERAL,
                    proposed_text=f"Add a {finding.clause_type} clause that follows the ACTA baseline.",
                    rationale=finding.detail,
                    confidence=0.7,
                    original_text="",
                    suggested_text=f"Add a {finding.clause_type} clause that follows the ACTA baseline.",
                    reason=finding.detail,
                    priority="high",
                )
            )
            seen_clause_ids.add(synthetic_id)

        return suggestions

    def _missing_clause_suggestions(self, compliance_findings: list[ComplianceFinding]) -> list[Suggestion]:
        suggestions: list[Suggestion] = []
        for finding in compliance_findings:
            if finding.status.lower() != "missing":
                continue
            suggestions.append(
                Suggestion(
                    clause_id=f"missing:{finding.clause_type.lower().replace(' ', '_')}",
                    clause_type=ClauseType.GENERAL,
                    proposed_text=f"Add a {finding.clause_type} clause that follows the ACTA baseline.",
                    rationale=finding.detail,
                    confidence=0.7,
                    original_text="",
                    suggested_text=f"Add a {finding.clause_type} clause that follows the ACTA baseline.",
                    reason=finding.detail,
                    priority="high",
                )
            )
        return suggestions

    def _dedupe_and_sort_suggestions(self, suggestions: list[Suggestion]) -> list[Suggestion]:
        deduped: dict[str, Suggestion] = {}
        for suggestion in suggestions:
            existing = deduped.get(suggestion.clause_id)
            if existing is None:
                deduped[suggestion.clause_id] = suggestion
                continue

            current_rank = PRIORITY_ORDER.get(suggestion.priority, 1)
            existing_rank = PRIORITY_ORDER.get(existing.priority, 1)
            if current_rank < existing_rank or suggestion.confidence > existing.confidence:
                deduped[suggestion.clause_id] = suggestion

        return sorted(
            deduped.values(),
            key=lambda suggestion: (
                PRIORITY_ORDER.get(suggestion.priority, 1),
                suggestion.clause_id,
            ),
        )

    def _generate_version_diff(self, suggestions: list[Suggestion]) -> str:
        diff_parts: list[str] = []

        for suggestion in suggestions:
            if suggestion.clause_id.startswith("missing:"):
                diff_parts.append(f"+ [Missing Clause] {suggestion.suggested_text}")
                continue

            original_lines = suggestion.original_text.splitlines()
            suggested_lines = suggestion.suggested_text.splitlines()
            if not original_lines and not suggested_lines:
                continue

            diff = difflib.unified_diff(
                original_lines,
                suggested_lines,
                fromfile=f"{suggestion.clause_id} (original)",
                tofile=f"{suggestion.clause_id} (suggested)",
                lineterm="",
            )
            diff_text = "\n".join(diff)
            if diff_text:
                diff_parts.append(diff_text)

        return "\n\n".join(diff_parts) if diff_parts else "No changes required."

    def _build_summary(self, state: ContractReviewState) -> str:
        if state.risk_summary:
            return state.risk_summary

        counts = Counter(finding.risk_level for finding in state.risk_findings)
        return (
            f"Reviewed {len(state.risk_findings)} clauses. "
            f"Detected {counts[RiskLevel.RED]} critical, {counts[RiskLevel.YELLOW]} minor, "
            f"and {counts[RiskLevel.GREEN]} aligned clauses."
        )

    def _clean_response_content(self, content: object) -> str:
        if isinstance(content, list):
            text = "".join(
                str(part.get("text", "")) if isinstance(part, dict) else str(getattr(part, "text", part))
                for part in content
            )
        else:
            text = str(content)

        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        return text.strip()

    def _normalize_priority(self, value: object) -> str:
        priority = str(value or "medium").strip().lower()
        if priority in PRIORITY_ORDER:
            return priority
        return "medium"
