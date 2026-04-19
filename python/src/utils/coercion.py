from __future__ import annotations

from src.pipeline.state import ClauseType


def coerce_clause_type(raw_value: str) -> ClauseType:
    normalized = raw_value.strip().lower()
    alias_map = {
        "confidentiality": ClauseType.CONFIDENTIALITY,
        "indemnification": ClauseType.INDEMNIFICATION,
        "payment terms": ClauseType.PAYMENT_TERMS,
        "payment": ClauseType.PAYMENT_TERMS,
        "intellectual property": ClauseType.INTELLECTUAL_PROPERTY,
        "publication rights": ClauseType.PUBLICATION_RIGHTS,
        "publication": ClauseType.PUBLICATION_RIGHTS,
        "termination": ClauseType.TERMINATION,
        "governing law": ClauseType.GOVERNING_LAW,
        "subject injury": ClauseType.SUBJECT_INJURY,
        "protocol deviations": ClauseType.PROTOCOL_DEVIATIONS,
        "general clause": ClauseType.GENERAL,
        "general": ClauseType.GENERAL,
    }
    return alias_map.get(normalized, ClauseType.GENERAL)


def coerce_confidence(value: object, fallback: float = 0.5) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = fallback
    return min(max(confidence, 0.0), 1.0)
