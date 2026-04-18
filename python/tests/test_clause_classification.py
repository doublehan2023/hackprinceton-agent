from src.nlp.legal_nlp import classify_clause, extract_clauses
from src.parsers.document_parser import parse_text
from src.pipeline.state import ClauseType


def test_classify_confidentiality_clause() -> None:
    clause = classify_clause(
        "Confidential information and proprietary materials must not be disclosed to third parties.",
        index=1,
    )

    assert clause.clause_type is ClauseType.CONFIDENTIALITY
    assert clause.source_order == 1
    assert "confidential" in clause.evidence


def test_classify_publication_clause() -> None:
    clause = classify_clause(
        "Publication of the manuscript requires sponsor review before the site may publish results.",
        index=2,
    )

    assert clause.clause_type is ClauseType.PUBLICATION_RIGHTS
    assert set(clause.evidence) == {"publication", "publish", "manuscript"}


def test_classify_general_clause_when_no_keywords_match() -> None:
    clause = classify_clause(
        "The parties will collaborate in good faith to support the study timeline and operations.",
        index=3,
    )

    assert clause.clause_type is ClauseType.GENERAL
    assert clause.evidence == []
    assert clause.classification_confidence == 0.4


def test_extract_clauses_respects_max_clause_limit() -> None:
    text = (
        "Confidential information must remain protected.\n\n"
        "Invoices are due within thirty days of receipt.\n\n"
        "The agreement terminates on thirty days notice."
    )

    clauses = extract_clauses(text, max_clauses=2)

    assert len(clauses) == 2
    assert [clause.source_order for clause in clauses] == [1, 2]


def test_classification_prefers_higher_keyword_frequency() -> None:
    clause = classify_clause(
        "Publication requires sponsor review. Publication delays may occur only for patent filings before publication.",
        index=4,
    )

    assert clause.clause_type is ClauseType.PUBLICATION_RIGHTS
    assert clause.classification_confidence > 0.45


def test_extract_clauses_preserves_section_context_and_order() -> None:
    parsed = parse_text(
        "1. Payment Terms\n"
        "Invoices are due within thirty days.\n\n"
        "2. Termination\n"
        "Either party may terminate this agreement with thirty days notice."
    )

    clauses = extract_clauses(parsed.raw_text, sections=parsed.sections, max_clauses=5)

    assert [clause.section_title for clause in clauses] == ["1. Payment Terms", "2. Termination"]
    assert [clause.section_order for clause in clauses] == [1, 2]
    assert [clause.source_order for clause in clauses] == [1, 2]
    assert clauses[0].clause_type is ClauseType.PAYMENT_TERMS
    assert clauses[1].clause_type is ClauseType.TERMINATION
