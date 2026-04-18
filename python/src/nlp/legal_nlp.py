from __future__ import annotations

import re

from src.pipeline.state import Clause, ClauseType


CLAUSE_KEYWORDS: dict[ClauseType, list[str]] = {
    ClauseType.CONFIDENTIALITY: ["confidential", "non-disclosure", "proprietary"],
    ClauseType.INDEMNIFICATION: ["indemn", "hold harmless", "liability"],
    ClauseType.PAYMENT_TERMS: ["payment", "invoice", "budget", "fees", "compensation"],
    ClauseType.INTELLECTUAL_PROPERTY: ["intellectual property", "ownership", "patent", "invention"],
    ClauseType.PUBLICATION_RIGHTS: ["publication", "publish", "manuscript"],
    ClauseType.TERMINATION: ["terminate", "termination", "end of agreement"],
    ClauseType.GOVERNING_LAW: ["governing law", "jurisdiction", "venue", "court"],
    ClauseType.SUBJECT_INJURY: ["injury", "medical care", "subject injury"],
    ClauseType.PROTOCOL_DEVIATIONS: ["protocol deviation", "deviation", "five business days"],
}


def split_into_blocks(text: str) -> list[str]:
    normalized = re.sub(r"\r\n?", "\n", text)
    blocks = [block.strip() for block in re.split(r"\n\s*\n", normalized) if block.strip()]
    if blocks:
        return blocks

    sentences = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text).strip())
    return [sentence.strip() for sentence in sentences if len(sentence.strip()) > 50]


def classify_clause(block: str, index: int) -> Clause:
    lowered = block.lower()
    best_type = ClauseType.GENERAL
    best_score = 0
    evidence: list[str] = []

    for clause_type, keywords in CLAUSE_KEYWORDS.items():
        hits = [keyword for keyword in keywords if keyword in lowered]
        score = sum(lowered.count(keyword) for keyword in hits)
        if score > best_score:
            best_type = clause_type
            best_score = score
            evidence = hits

    confidence = min(0.45 + (0.15 * best_score), 0.95) if best_score else 0.4
    return Clause(
        id=f"clause-{index}",
        clause_type=best_type,
        text=block,
        source_order=index,
        evidence=evidence,
        classification_confidence=confidence,
    )


def extract_clauses(text: str, *, max_clauses: int) -> list[Clause]:
    blocks = split_into_blocks(text)
    clauses = [classify_clause(block, index) for index, block in enumerate(blocks, start=1)]
    return clauses[:max_clauses]
