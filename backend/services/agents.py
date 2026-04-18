import re

from backend.core.config import get_settings
from backend.repository import get_recent_annotation_examples
from backend.schemas import (
    ClassifiedClause,
    ClauseAssessment,
    ClauseMap,
    ClauseType,
    ReasoningTrace,
    RedlineDraft,
    RiskLevel,
)
from backend.services.acta_playbook import ACTA_PLAYBOOK, CORE_CLAUSE_TYPES


CLAUSE_KEYWORDS: dict[ClauseType, list[str]] = {
    ClauseType.confidentiality: ["confidential", "non-disclosure", "proprietary"],
    ClauseType.indemnification: ["indemn", "hold harmless", "liability"],
    ClauseType.payment_terms: ["payment", "invoice", "budget", "fees", "compensation"],
    ClauseType.intellectual_property: ["intellectual property", "ownership", "patent", "invention"],
    ClauseType.publication_rights: ["publication", "publish", "manuscript"],
    ClauseType.termination: ["terminate", "termination", "end of agreement"],
    ClauseType.governing_law: ["governing law", "jurisdiction", "venue", "court"],
    ClauseType.subject_injury: ["injury", "medical care", "subject injury"],
    ClauseType.protocol_deviations: ["protocol deviation", "deviation", "five business days"],
}


def _split_into_blocks(text: str) -> list[str]:
    normalized = re.sub(r"\r\n?", "\n", text)
    blocks = [block.strip() for block in re.split(r"\n\s*\n", normalized) if block.strip()]
    if blocks:
        return blocks

    sentences = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text).strip())
    return [sentence.strip() for sentence in sentences if len(sentence.strip()) > 50]


def _classify_block(block: str, index: int) -> ClassifiedClause:
    lowered = block.lower()
    best_type = ClauseType.general
    best_score = 0
    evidence: list[str] = []

    for clause_type, keywords in CLAUSE_KEYWORDS.items():
        hits = [keyword for keyword in keywords if keyword in lowered]
        if len(hits) > best_score:
            best_type = clause_type
            best_score = len(hits)
            evidence = hits

    confidence = min(0.45 + (0.15 * best_score), 0.95) if best_score else 0.4
    return ClassifiedClause(
        clause_type=best_type,
        raw_text=block,
        source_order=index,
        classification_confidence=confidence,
        evidence=evidence,
    )


def classify_document(text: str) -> ClauseMap:
    clauses = [_classify_block(block, index) for index, block in enumerate(_split_into_blocks(text), start=1)]
    seen_types = {clause.clause_type for clause in clauses}
    missing = [clause_type for clause_type in CORE_CLAUSE_TYPES if clause_type not in seen_types]
    return ClauseMap(clauses=clauses[: get_settings().analysis_max_clauses], missing_clause_types=missing)


def analyze_clause(classified_clause: ClassifiedClause) -> ClauseAssessment:
    playbook = ACTA_PLAYBOOK[classified_clause.clause_type]
    standard_text = str(playbook["standard_text"])
    required_terms = [term.lower() for term in playbook["required_terms"]]
    clause_text_lower = classified_clause.raw_text.lower()

    matched_terms = [term for term in required_terms if term in clause_text_lower]
    missing_terms = [term for term in required_terms if term not in clause_text_lower]

    if not required_terms:
        risk_level = RiskLevel.yellow
        risk_score = 0.55
        deviation_summary = "Clause needs human mapping to the closest ACTA section."
        suggested_action = "Route for manual legal review."
    elif len(matched_terms) == len(required_terms):
        risk_level = RiskLevel.green
        risk_score = 0.2
        deviation_summary = "Clause is broadly aligned with the ACTA baseline."
        suggested_action = "No redline required."
    elif matched_terms:
        risk_level = RiskLevel.yellow
        risk_score = 0.58 + (0.08 * len(missing_terms))
        deviation_summary = "Clause partially aligns with ACTA but misses important baseline protections."
        suggested_action = "Show ACTA-anchored fallback text if confidence clears the gate."
    else:
        risk_level = RiskLevel.red
        risk_score = 0.82
        deviation_summary = "Clause materially departs from the ACTA baseline or omits core protections."
        suggested_action = "Escalate and propose baseline replacement language."

    examples = get_recent_annotation_examples(
        classified_clause.clause_type.value,
        get_settings().annotation_example_limit,
    )
    confidence = max(
        0.35,
        min(
            0.95,
            classified_clause.classification_confidence
            + (0.15 if matched_terms else 0.0)
            + (0.05 * min(len(examples), 2))
            - (0.1 * min(len(missing_terms), 3)),
        ),
    )

    critic_notes = []
    if missing_terms:
        critic_notes.append(f"Missing baseline terms: {', '.join(missing_terms)}")
    if classified_clause.clause_type is ClauseType.general:
        critic_notes.append("Classifier could not confidently map this text to a core ACTA clause type.")

    human_review_required = confidence < get_settings().confidence_threshold

    reasoning = ReasoningTrace(
        acta_standard_excerpt=standard_text,
        deviation_detected=deviation_summary,
        why_it_matters=(
            "Missing baseline protections can increase negotiation time, create legal exposure, or move the CTA away "
            "from ACTA-preferred language."
        ),
        confidence_factors=[
            f"Matched terms: {', '.join(matched_terms) if matched_terms else 'none'}",
            f"Annotation examples injected: {len(examples)}",
            f"Classifier confidence: {classified_clause.classification_confidence:.2f}",
        ],
    )

    return ClauseAssessment(
        clause_type=classified_clause.clause_type,
        raw_text=classified_clause.raw_text,
        risk_level=risk_level,
        risk_score=min(risk_score, 0.99),
        deviation_summary=deviation_summary,
        suggested_action=suggested_action,
        reasoning_trace=reasoning,
        confidence=confidence,
        critic_notes=critic_notes,
        human_review_required=human_review_required,
    )


def generate_redline(assessment: ClauseAssessment) -> RedlineDraft | None:
    if assessment.risk_level == RiskLevel.green:
        return None
    if assessment.human_review_required:
        return None

    playbook = ACTA_PLAYBOOK[assessment.clause_type]
    proposed_text = str(playbook["standard_text"])
    return RedlineDraft(
        clause_type=assessment.clause_type,
        original_text=assessment.raw_text,
        proposed_text=proposed_text,
        rationale="Replacement text is anchored directly to the ACTA baseline for this clause type.",
        confidence=min(assessment.confidence, 0.95),
        source="acta_baseline",
    )
