from __future__ import annotations

import json
import logging
import re

from src.config import get_llm, get_settings
from src.pipeline.state import Clause, ClauseType, ContractReviewState, RiskFinding, RiskLevel
from src.rules.engine import PLAYBOOK, evaluate_clause_risk

logger = logging.getLogger(__name__)

try:
    from langchain_core.messages import HumanMessage, SystemMessage
except ImportError:  # pragma: no cover - optional dependency in local test env
    HumanMessage = None
    SystemMessage = None


SYSTEM_PROMPT = """You are a legal risk reviewer for clinical trial agreements.

Review each clause against the ACTA baseline for its clause type. Return valid JSON only.

Use this schema exactly:
{
  "findings": [
    {
      "clause_id": "clause-1",
      "risk_level": "red|yellow|green",
      "risk_type": "short risk label",
      "description": "how the clause deviates from the ACTA baseline",
      "buyer_impact": "impact on the sponsor or drafting party",
      "seller_impact": "impact on the site or counterparty",
      "rationale": "why this is a risk relative to the ACTA baseline",
      "suggested_action": "practical next step",
      "confidence": 0.0
    }
  ],
  "overall_risk_level": "red|yellow|green",
  "risk_summary": "one sentence summary"
}

Rules:
- Return JSON only, with no markdown fences.
- Provide one finding for each clause_id in the input.
- Use green when the clause is materially aligned with the ACTA baseline.
- Use yellow for partial deviations or missing protective terms.
- Use red for strongly one-sided language, open-ended liability, weak publication/termination protections, or other material departures from the ACTA baseline.
- Keep confidence between 0 and 1.
"""


ACTA_RISK_RULES: dict[ClauseType, list[dict[str, object]]] = {
    ClauseType.INDEMNIFICATION: [
        {
            "name": "unlimited_liability",
            "patterns": [r"unlimited liability", r"without limitation", r"all losses", r"any and all liability"],
            "risk_level": RiskLevel.RED,
            "summary": "The clause creates exposure beyond the ACTA baseline's negligence-based allocation.",
            "buyer_impact": "The drafting party may face uncapped indemnity or defense exposure.",
            "seller_impact": "The counterparty can shift broad downstream liability without a matching cap or fault standard.",
            "action": "Cap liability and restore mutual, negligence-based indemnification language.",
        },
        {
            "name": "one_way_indemnity",
            "patterns": [r"shall indemnify", r"defend and hold harmless"],
            "risk_level": RiskLevel.YELLOW,
            "summary": "The clause appears one-sided compared with ACTA's mutual indemnity position.",
            "buyer_impact": "The drafting party may absorb product or negligence risk without reciprocity.",
            "seller_impact": "The counterparty receives broader protection than the ACTA baseline normally provides.",
            "action": "Reframe indemnity as mutual and tie it to negligence or product liability.",
        },
    ],
    ClauseType.TERMINATION: [
        {
            "name": "unilateral_termination",
            "patterns": [r"terminate at any time", r"sole discretion", r"without cause", r"immediately terminate"],
            "risk_level": RiskLevel.RED,
            "summary": "The clause gives one party unilateral termination rights that exceed ACTA's balanced termination framework.",
            "buyer_impact": "The drafting party may lose continuity, budget certainty, or patient safety protections.",
            "seller_impact": "The counterparty can exit without reciprocal notice or transition duties.",
            "action": "Add notice periods, patient protection steps, and post-termination obligations.",
        },
    ],
    ClauseType.PUBLICATION_RIGHTS: [
        {
            "name": "publication_veto",
            "patterns": [r"prior written consent", r"may withhold publication", r"approve any publication", r"sole discretion"],
            "risk_level": RiskLevel.RED,
            "summary": "The clause looks more restrictive than ACTA's limited review and patent-delay approach.",
            "buyer_impact": "The drafting party may lose academic publication rights or timeline control.",
            "seller_impact": "The counterparty gains a de facto veto over publication.",
            "action": "Limit review rights to a short comment period and patent filing delay only.",
        },
    ],
    ClauseType.GOVERNING_LAW: [
        {
            "name": "exclusive_venue",
            "patterns": [r"exclusive jurisdiction", r"exclusive venue", r"sole venue"],
            "risk_level": RiskLevel.YELLOW,
            "summary": "The clause can impose a one-sided litigation burden compared with the ACTA baseline.",
            "buyer_impact": "The drafting party may have to litigate in an unfavorable or distant forum.",
            "seller_impact": "The counterparty secures procedural leverage on venue.",
            "action": "Negotiate a neutral venue or commercially reasonable governing-law compromise.",
        },
    ],
    ClauseType.PAYMENT_TERMS: [
        {
            "name": "extended_payment_timeline",
            "patterns": [r"net 60", r"net 90", r"sixty days", r"ninety days"],
            "risk_level": RiskLevel.YELLOW,
            "summary": "The payment timing is slower than ACTA's net-30 style baseline.",
            "buyer_impact": "The drafting party may wait longer for reimbursement and carry performance costs.",
            "seller_impact": "The counterparty preserves cash-flow leverage.",
            "action": "Restore net-30 timing and tie payment to itemized invoicing.",
        },
    ],
    ClauseType.CONFIDENTIALITY: [
        {
            "name": "weak_confidentiality_protection",
            "patterns": [r"as it deems appropriate", r"reasonable efforts only", r"commercially reasonable efforts only"],
            "risk_level": RiskLevel.YELLOW,
            "summary": "The confidentiality protection may be weaker than the ACTA baseline.",
            "buyer_impact": "The drafting party may have reduced recourse if confidential information is mishandled.",
            "seller_impact": "The counterparty carries a lighter protection standard than ACTA typically expects.",
            "action": "Use clearer confidentiality obligations and standard ACTA exceptions.",
        },
    ],
}

RISK_PRIORITY = {
    RiskLevel.RED: 3,
    RiskLevel.YELLOW: 2,
    RiskLevel.GREEN: 1,
}


class RiskIdentificationAgent:
    def __init__(self) -> None:
        self.llm = None
        self.analysis_model = "k2"

    def _ensure_llm(self) -> None:
        settings = get_settings()
        self.analysis_model = settings.llm_provider
        if settings.llm_provider != "k2":
            raise RuntimeError("Risk identification requires K2. Set K2_API_KEY to enable K2 analysis.")
        if self.llm is None:
            self.llm = get_llm()
        if self.llm is None:
            raise RuntimeError("Risk identification requires K2, but the K2 client is unavailable.")

    def __call__(self, state: ContractReviewState) -> dict[str, object]:
        logger.info("Starting ACTA-based risk identification for review_id=%s", state.review_id)

        if not state.clauses:
            summary = "Reviewed 0 clauses. No clauses were available for ACTA baseline comparison."
            return {
                "risk_findings": [],
                "overall_risk_level": RiskLevel.GREEN,
                "risk_summary": summary,
                "summary": summary,
                "needs_human_review": False,
            }

        rule_findings = self._rule_based_scan(state.clauses)

        try:
            self._ensure_llm()
        except Exception as exc:
            overall = self._calculate_overall_risk(rule_findings)
            summary = self._generate_k2_required_summary(rule_findings, overall)
            return {
                "risk_findings": rule_findings,
                "overall_risk_level": overall,
                "risk_summary": summary,
                "summary": summary,
                "needs_human_review": True,
                "errors": state.errors + [str(exc)],
            }

        try:
            llm_findings = self._llm_analysis(state.clauses)
            merged = self._merge_findings(state.clauses, rule_findings, llm_findings)
            overall = self._calculate_overall_risk(merged)
            summary = self._generate_summary(merged, overall)
            return {
                "risk_findings": merged,
                "overall_risk_level": overall,
                "risk_summary": summary,
                "summary": summary,
                "needs_human_review": any(f.needs_human_review for f in merged),
            }
        except Exception as exc:  # pragma: no cover - exercised by integration behavior
            logger.warning("%s risk analysis failed; provisional ACTA rules only: %s", self.analysis_model.upper(), exc)
            overall = self._calculate_overall_risk(rule_findings)
            summary = self._generate_k2_required_summary(rule_findings, overall)
            return {
                "risk_findings": rule_findings,
                "overall_risk_level": overall,
                "risk_summary": summary,
                "summary": summary,
                "needs_human_review": True,
                "errors": state.errors + [f"Risk identification K2 analysis failed: {exc}"],
            }

    def _rule_based_scan(self, clauses: list[Clause]) -> list[RiskFinding]:
        findings: list[RiskFinding] = []

        for clause in clauses:
            baseline = evaluate_clause_risk(clause)
            finding = baseline.model_copy(
                update={
                    "risk_type": "acta_alignment",
                    "rationale": self._build_baseline_rationale(baseline),
                    "buyer_impact": self._default_buyer_impact(baseline),
                    "seller_impact": self._default_seller_impact(baseline),
                    "engine": "rules",
                }
            )

            for rule in ACTA_RISK_RULES.get(clause.clause_type, []):
                if self._matches_rule(clause.text, rule["patterns"]):
                    finding = self._apply_rule_override(finding, clause, rule)

            findings.append(finding)

        return findings

    def _matches_rule(self, clause_text: str, patterns: list[object]) -> bool:
        text = clause_text.lower()
        for pattern in patterns:
            if re.search(str(pattern), text):
                return True
        return False

    def _apply_rule_override(self, finding: RiskFinding, clause: Clause, rule: dict[str, object]) -> RiskFinding:
        level = rule["risk_level"]
        summary = str(rule["summary"])
        buyer_impact = str(rule["buyer_impact"])
        seller_impact = str(rule["seller_impact"])
        action = str(rule["action"])
        rationale = (
            f"ACTA rule trigger for {clause.clause_type.value}: "
            f"{summary}"
        )

        if RISK_PRIORITY[level] >= RISK_PRIORITY[finding.risk_level]:
            return finding.model_copy(
                update={
                    "risk_level": level,
                    "deviation_summary": summary,
                    "suggested_action": action,
                    "confidence": max(finding.confidence, 0.82 if level is RiskLevel.RED else 0.74),
                    "needs_human_review": True,
                    "risk_type": str(rule["name"]),
                    "rationale": rationale,
                    "buyer_impact": buyer_impact,
                    "seller_impact": seller_impact,
                    "engine": "rules",
                }
            )

        combined_rationale = f"{finding.rationale} {rationale}".strip()
        return finding.model_copy(update={"rationale": combined_rationale})

    def _build_baseline_rationale(self, finding: RiskFinding) -> str:
        if finding.risk_level is RiskLevel.GREEN:
            return "The clause covers the core protections expected by the ACTA baseline for this clause type."
        if finding.missing_terms:
            missing = ", ".join(finding.missing_terms[:3])
            return f"The clause misses ACTA baseline protections tied to: {missing}."
        return "The clause departs from the ACTA baseline and needs legal review."

    def _default_buyer_impact(self, finding: RiskFinding) -> str:
        if finding.risk_level is RiskLevel.GREEN:
            return "No material deviation from the ACTA baseline was detected for the drafting party."
        return "The drafting party may lose some ACTA-aligned contractual protection."

    def _default_seller_impact(self, finding: RiskFinding) -> str:
        if finding.risk_level is RiskLevel.GREEN:
            return "The clause appears balanced against the ACTA baseline."
        return "The counterparty may retain leverage because the clause is less protective than the ACTA baseline."

    def _llm_analysis(self, clauses: list[Clause]) -> list[RiskFinding]:
        if HumanMessage is not None and SystemMessage is not None:
            messages = [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=self._build_llm_prompt(clauses)),
            ]
        else:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": self._build_llm_prompt(clauses)},
            ]

        response = self.llm.invoke(messages)
        content = self._coerce_response_content(response)
        payload = json.loads(self._strip_code_fences(content))

        findings: list[RiskFinding] = []
        clause_lookup = {clause.id: clause for clause in clauses}

        for item in payload.get("findings", []):
            if not isinstance(item, dict):
                continue

            clause_id = str(item.get("clause_id", "")).strip()
            clause = clause_lookup.get(clause_id)
            if clause is None:
                continue

            level = self._coerce_risk_level(item.get("risk_level"))
            description = str(item.get("description", "")).strip() or "Clause reviewed against the ACTA baseline."
            action = str(item.get("suggested_action", "")).strip() or self._default_action(level, clause.clause_type)
            confidence = self._coerce_confidence(item.get("confidence"), clause.classification_confidence)

            findings.append(
                RiskFinding(
                    clause_id=clause.id,
                    clause_type=clause.clause_type,
                    clause_text=clause.text,
                    risk_level=level,
                    deviation_summary=description,
                    suggested_action=action,
                    confidence=confidence,
                    needs_human_review=level is RiskLevel.RED or confidence < get_settings().confidence_threshold,
                    matched_terms=[],
                    missing_terms=[],
                    risk_type=str(item.get("risk_type", "acta_alignment")).strip() or "acta_alignment",
                    rationale=str(item.get("rationale", "")).strip(),
                    buyer_impact=str(item.get("buyer_impact", "")).strip(),
                    seller_impact=str(item.get("seller_impact", "")).strip(),
                    engine=self.analysis_model,
                )
            )

        return findings

    def _build_llm_prompt(self, clauses: list[Clause]) -> str:
        chunks: list[str] = []
        for clause in clauses:
            playbook = PLAYBOOK[clause.clause_type]
            required_terms = ", ".join(playbook["required_terms"]) or "none"
            chunks.append(
                f"[Clause ID: {clause.id}]\n"
                f"Clause Type: {clause.clause_type.value}\n"
                f"ACTA Baseline: {playbook['standard_text']}\n"
                f"Expected Terms: {required_terms}\n"
                f"Clause Text: {clause.text}"
            )
        return "Review these clauses against their ACTA baselines:\n\n" + "\n\n".join(chunks)

    def _coerce_response_content(self, response: object) -> str:
        content = getattr(response, "content", response)
        if isinstance(content, list):
            parts: list[str] = []
            for part in content:
                if isinstance(part, dict):
                    parts.append(str(part.get("text", "")))
                else:
                    text = getattr(part, "text", None)
                    parts.append(str(text if text is not None else part))
            content = "".join(parts)
        elif not isinstance(content, str):
            content = str(content)

        text = content.strip()
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
        if "</think>" in text.lower():
            parts = re.split(r"</think>", text, flags=re.IGNORECASE, maxsplit=1)
            text = parts[-1].strip()
        return text

    def _strip_code_fences(self, content: str) -> str:
        if content.startswith("```"):
            lines = content.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            return "\n".join(lines).strip()
        return content.strip()

    def _coerce_risk_level(self, value: object) -> RiskLevel:
        normalized = str(value).strip().lower()
        if normalized == RiskLevel.RED.value:
            return RiskLevel.RED
        if normalized == RiskLevel.YELLOW.value:
            return RiskLevel.YELLOW
        return RiskLevel.GREEN

    def _coerce_confidence(self, value: object, fallback: float) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            confidence = min(0.9, max(0.55, fallback))
        return min(max(confidence, 0.0), 1.0)

    def _default_action(self, level: RiskLevel, clause_type: ClauseType) -> str:
        if level is RiskLevel.GREEN:
            return "No redline required."
        standard_text = str(PLAYBOOK[clause_type]["standard_text"])
        if level is RiskLevel.RED:
            return f"Escalate and replace with ACTA baseline language: {standard_text}"
        return f"Align this clause more closely with the ACTA baseline: {standard_text}"

    def _merge_findings(
        self,
        clauses: list[Clause],
        rule_findings: list[RiskFinding],
        llm_findings: list[RiskFinding],
    ) -> list[RiskFinding]:
        merged: dict[str, RiskFinding] = {finding.clause_id: finding for finding in rule_findings}

        for llm_finding in llm_findings:
            existing = merged.get(llm_finding.clause_id)
            if existing is None:
                merged[llm_finding.clause_id] = llm_finding
                continue

            updates: dict[str, object] = {}
            if RISK_PRIORITY[llm_finding.risk_level] > RISK_PRIORITY[existing.risk_level]:
                updates["risk_level"] = llm_finding.risk_level
                updates["deviation_summary"] = llm_finding.deviation_summary
                updates["suggested_action"] = llm_finding.suggested_action
                updates["risk_type"] = llm_finding.risk_type
                updates["buyer_impact"] = llm_finding.buyer_impact or existing.buyer_impact
                updates["seller_impact"] = llm_finding.seller_impact or existing.seller_impact
                updates["rationale"] = llm_finding.rationale or existing.rationale
                updates["needs_human_review"] = llm_finding.needs_human_review or existing.needs_human_review

            elif llm_finding.risk_level is existing.risk_level:
                if llm_finding.rationale and llm_finding.rationale not in existing.rationale:
                    updates["rationale"] = f"{existing.rationale} {llm_finding.rationale}".strip()
                if llm_finding.buyer_impact:
                    updates["buyer_impact"] = llm_finding.buyer_impact
                if llm_finding.seller_impact:
                    updates["seller_impact"] = llm_finding.seller_impact
                if llm_finding.risk_type and existing.risk_type == "acta_alignment":
                    updates["risk_type"] = llm_finding.risk_type

            updates["confidence"] = max(existing.confidence, llm_finding.confidence)
            updates["engine"] = "merged"
            if updates:
                merged[llm_finding.clause_id] = existing.model_copy(update=updates)

        ordered: list[RiskFinding] = []
        for clause in clauses:
            finding = merged.get(clause.id)
            if finding is not None:
                ordered.append(finding)
        return ordered

    def _calculate_overall_risk(self, findings: list[RiskFinding]) -> RiskLevel:
        if any(finding.risk_level is RiskLevel.RED for finding in findings):
            return RiskLevel.RED
        if any(finding.risk_level is RiskLevel.YELLOW for finding in findings):
            return RiskLevel.YELLOW
        return RiskLevel.GREEN

    def _generate_summary(self, findings: list[RiskFinding], overall: RiskLevel) -> str:
        red = sum(1 for finding in findings if finding.risk_level is RiskLevel.RED)
        yellow = sum(1 for finding in findings if finding.risk_level is RiskLevel.YELLOW)
        green = sum(1 for finding in findings if finding.risk_level is RiskLevel.GREEN)
        return (
            f"Reviewed {len(findings)} clauses. "
            f"Compared them against the ACTA baseline and detected "
            f"{red} critical, {yellow} moderate, and {green} aligned clauses. "
            f"Overall ACTA deviation risk is {overall.value}."
        )

    def _generate_k2_required_summary(self, findings: list[RiskFinding], overall: RiskLevel) -> str:
        red = sum(1 for finding in findings if finding.risk_level is RiskLevel.RED)
        yellow = sum(1 for finding in findings if finding.risk_level is RiskLevel.YELLOW)
        green = sum(1 for finding in findings if finding.risk_level is RiskLevel.GREEN)
        return (
            f"Reviewed {len(findings)} clauses. "
            f"K2 analysis is required for final ACTA risk identification and was unavailable, "
            f"so these results are provisional rule-based screening only: "
            f"{red} critical, {yellow} moderate, and {green} aligned clauses. "
            f"Provisional ACTA deviation risk is {overall.value}."
        )
