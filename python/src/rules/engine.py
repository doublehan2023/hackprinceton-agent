from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from src.config import get_settings
from src.pipeline.state import Clause, ClauseType, RiskFinding, RiskLevel, Suggestion

RULESET_VERSION = "v1"
RULESET_DIR = Path(__file__).with_name("data") / RULESET_VERSION

@lru_cache(maxsize=1)
def _load_playbook() -> dict[ClauseType, dict[str, object]]:
    payload = json.loads((RULESET_DIR / "playbook.json").read_text(encoding="utf-8"))
    return {
        ClauseType(clause_type): {
            "standard_text": str(item["standard_text"]),
            "required_terms": [str(term) for term in item.get("required_terms", [])],
        }
        for clause_type, item in payload.items()
    }


@lru_cache(maxsize=1)
def _load_risk_rules() -> dict[ClauseType, list[dict[str, object]]]:
    payload = json.loads((RULESET_DIR / "risk_rules.json").read_text(encoding="utf-8"))
    return {
        ClauseType(clause_type): [
            {
                "name": str(item["name"]),
                "patterns": [str(pattern) for pattern in item.get("patterns", [])],
                "risk_level": RiskLevel(str(item["risk_level"])),
                "summary": str(item["summary"]),
                "buyer_impact": str(item["buyer_impact"]),
                "seller_impact": str(item["seller_impact"]),
                "action": str(item["action"]),
            }
            for item in rules
        ]
        for clause_type, rules in payload.items()
    }


PLAYBOOK = _load_playbook()
ACTA_RISK_RULES = _load_risk_rules()

CORE_CLAUSE_TYPES = [
    ClauseType.CONFIDENTIALITY,
    ClauseType.INDEMNIFICATION,
    ClauseType.PAYMENT_TERMS,
    ClauseType.INTELLECTUAL_PROPERTY,
    ClauseType.PUBLICATION_RIGHTS,
    ClauseType.TERMINATION,
    ClauseType.GOVERNING_LAW,
]


def evaluate_clause_risk(clause: Clause) -> RiskFinding:
    playbook = PLAYBOOK[clause.clause_type]
    required_terms = [term.lower() for term in playbook["required_terms"]]
    clause_text_lower = clause.text.lower()

    matched_terms = [term for term in required_terms if term in clause_text_lower]
    missing_terms = [term for term in required_terms if term not in clause_text_lower]

    if not required_terms:
        risk_level = RiskLevel.YELLOW
        deviation_summary = "Clause needs manual mapping to the closest CTA baseline section."
        suggested_action = "Route this clause for legal review."
        confidence = 0.5
    elif len(matched_terms) == len(required_terms):
        risk_level = RiskLevel.GREEN
        deviation_summary = "Clause appears aligned with the preferred CTA baseline."
        suggested_action = "No redline required."
        confidence = min(0.95, clause.classification_confidence + 0.2)
    elif matched_terms:
        risk_level = RiskLevel.YELLOW
        deviation_summary = "Clause partially aligns with the preferred CTA baseline but misses protective terms."
        suggested_action = "Review fallback language and negotiate the missing protections."
        confidence = min(0.9, clause.classification_confidence + 0.05)
    else:
        risk_level = RiskLevel.RED
        deviation_summary = "Clause materially departs from the preferred CTA baseline or omits core protections."
        suggested_action = "Escalate this clause and propose replacement language."
        confidence = max(0.45, clause.classification_confidence - 0.05)

    needs_human_review = (
        confidence < get_settings().confidence_threshold
        or clause.clause_type is ClauseType.GENERAL
    )

    return RiskFinding(
        clause_id=clause.id,
        clause_type=clause.clause_type,
        clause_text=clause.text,
        risk_level=risk_level,
        deviation_summary=deviation_summary,
        suggested_action=suggested_action,
        confidence=confidence,
        needs_human_review=needs_human_review,
        matched_terms=matched_terms,
        missing_terms=missing_terms,
    )


def find_missing_clause_types(clauses: list[Clause]) -> list[str]:
    seen = {clause.clause_type for clause in clauses}
    return [clause_type.value for clause_type in CORE_CLAUSE_TYPES if clause_type not in seen]


def build_suggestion_for_finding(finding: RiskFinding) -> Suggestion | None:
    if finding.risk_level is RiskLevel.GREEN or finding.needs_human_review:
        return None

    playbook = PLAYBOOK[finding.clause_type]
    return Suggestion(
        clause_id=finding.clause_id,
        clause_type=finding.clause_type,
        proposed_text=str(playbook["standard_text"]),
        rationale="Suggested language is anchored to the project’s preferred CTA baseline for this clause type.",
        confidence=min(0.95, finding.confidence),
    )
