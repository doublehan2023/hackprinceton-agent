from __future__ import annotations

from src.config import get_settings
from src.pipeline.state import Clause, ClauseType, RiskFinding, RiskLevel, Suggestion


PLAYBOOK: dict[ClauseType, dict[str, object]] = {
    ClauseType.CONFIDENTIALITY: {
        "standard_text": (
            "Confidential information must remain protected for five years, excluding information "
            "that is publicly known, independently developed, or rightfully received from a third party."
        ),
        "required_terms": ["five years", "publicly known", "independently developed"],
    },
    ClauseType.INDEMNIFICATION: {
        "standard_text": (
            "Indemnification should be mutual and negligence-based only. The sponsor indemnifies "
            "for product liability, and neither party gives blanket indemnification."
        ),
        "required_terms": ["mutual", "negligence", "product liability"],
    },
    ClauseType.PAYMENT_TERMS: {
        "standard_text": (
            "Invoices should be paid within net 30 days and tied to an itemized budget with agreed caps on indirect costs."
        ),
        "required_terms": ["net 30", "itemized budget", "invoice"],
    },
    ClauseType.INTELLECTUAL_PROPERTY: {
        "standard_text": (
            "The sponsor retains rights to the investigational compound, while the site retains rights "
            "to independently developed intellectual property."
        ),
        "required_terms": ["sponsor retains", "independently developed", "intellectual property"],
    },
    ClauseType.PUBLICATION_RIGHTS: {
        "standard_text": (
            "The site receives a 60-day review period before publication, and any publication delay should be limited to patent filing needs."
        ),
        "required_terms": ["60-day", "publication", "patent"],
    },
    ClauseType.TERMINATION: {
        "standard_text": (
            "Termination rights should define notice requirements, patient safety protections, and post-termination obligations."
        ),
        "required_terms": ["notice", "patient safety", "termination"],
    },
    ClauseType.GOVERNING_LAW: {
        "standard_text": (
            "Governing law and venue should be commercially reasonable and should not create a one-sided litigation burden."
        ),
        "required_terms": ["governing law", "venue"],
    },
    ClauseType.SUBJECT_INJURY: {
        "standard_text": (
            "The sponsor covers research-related injury costs, except for harm caused solely by site negligence or standard-of-care obligations."
        ),
        "required_terms": ["research-related injury", "standard of care"],
    },
    ClauseType.PROTOCOL_DEVIATIONS: {
        "standard_text": "Protocol deviations must be reported to the sponsor within five business days.",
        "required_terms": ["protocol deviation", "five business days", "reported"],
    },
    ClauseType.GENERAL: {
        "standard_text": "Review this clause against the closest CTA baseline and escalate uncertainty.",
        "required_terms": [],
    },
}

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
