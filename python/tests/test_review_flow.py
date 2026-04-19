from __future__ import annotations

from src.agents.clause_extraction import ClauseExtractionAgent
from src.agents.compliance_check import ComplianceCheckAgent
from src.agents.risk_identification import RiskIdentificationAgent
from src.agents.suggestion import SuggestionAgent
from src.parsers.document_parser import parse_text
from src.pipeline.state import Clause, ClauseType, ComplianceFinding, ContractReviewState, RiskFinding, RiskLevel


def test_review_flow_handles_inline_text_with_headings() -> None:
    parsed = parse_text(
        "1. Confidentiality\n"
        "Confidential information must remain protected.\n\n"
        "2. Payment Terms\n"
        "Invoices are due within thirty days."
    )
    state = ContractReviewState(review_id="review-1", filename="inline.txt", raw_text=parsed.raw_text, sections=parsed.sections)

    state = state.model_copy(update=ClauseExtractionAgent()(state))
    state = state.model_copy(update=RiskIdentificationAgent()(state))
    state = state.model_copy(update=ComplianceCheckAgent()(state))
    state = state.model_copy(update=SuggestionAgent()(state))

    assert len(state.clauses) == 2
    assert state.summary.startswith("Reviewed 2 clauses.")
    assert {clause.section_title for clause in state.clauses} == {"1. Confidentiality", "2. Payment Terms"}


def test_clause_extraction_agent_can_use_llm_response() -> None:
    parsed = parse_text(
        "1. Confidentiality\n"
        "Confidential information must remain protected.\n\n"
        "2. Payment Terms\n"
        "Invoices are due within thirty days."
    )
    state = ContractReviewState(review_id="review-llm", filename="inline.txt", raw_text=parsed.raw_text, sections=parsed.sections)

    class FakeResponse:
        content = """
        {
          "clauses": [
            {
              "text": "Confidential information must remain protected.",
              "clause_type": "Confidentiality",
              "section_title": "1. Confidentiality",
              "section_order": 1,
              "evidence": ["confidential information"],
              "classification_confidence": 0.91
            },
            {
              "text": "Invoices are due within thirty days.",
              "clause_type": "Payment Terms",
              "section_title": "2. Payment Terms",
              "section_order": 2,
              "evidence": ["invoices"],
              "classification_confidence": 0.88
            }
          ]
        }
        """

    class FakeLLM:
        def invoke(self, messages):
            assert len(messages) == 2
            return FakeResponse()

    agent = ClauseExtractionAgent()
    agent.llm = FakeLLM()

    result = agent(state)

    assert len(result["clauses"]) == 2
    assert result["extraction_model"] == "llm"
    assert result["clauses"][0].clause_type is ClauseType.CONFIDENTIALITY
    assert result["clauses"][1].clause_type is ClauseType.PAYMENT_TERMS
    assert result["clauses"][0].section_order == 1
    assert result["clauses"][1].section_order == 2


def test_clause_extraction_agent_strips_k2_think_blocks() -> None:
    parsed = parse_text("1. Confidentiality\nConfidential information must remain protected.")
    state = ContractReviewState(review_id="review-k2", filename="inline.txt", raw_text=parsed.raw_text, sections=parsed.sections)

    class FakeResponse:
        content = """
        <think>I should classify this carefully.</think>
        {
          "clauses": [
            {
              "text": "Confidential information must remain protected.",
              "clause_type": "Confidentiality",
              "section_title": "1. Confidentiality",
              "section_order": 1,
              "evidence": ["confidential information"],
              "classification_confidence": 0.93
            }
          ]
        }
        """

    class FakeLLM:
        def invoke(self, messages):
            assert len(messages) == 2
            return FakeResponse()

    agent = ClauseExtractionAgent()
    agent.llm = FakeLLM()
    agent.extraction_model = "k2"

    result = agent(state)

    assert len(result["clauses"]) == 1
    assert result["extraction_model"] == "k2"
    assert result["clauses"][0].clause_type is ClauseType.CONFIDENTIALITY


def test_suggestion_agent_parses_llm_redlines() -> None:
    state = ContractReviewState(
        review_id="review-suggestions",
        raw_text="Test contract",
        clauses=[
            Clause(
                id="clause-1",
                clause_type=ClauseType.CONFIDENTIALITY,
                text="Recipient may use confidential information as it deems appropriate.",
                source_order=1,
                classification_confidence=0.91,
            )
        ],
        risk_findings=[
            RiskFinding(
                clause_id="clause-1",
                clause_type=ClauseType.CONFIDENTIALITY,
                clause_text="Recipient may use confidential information as it deems appropriate.",
                risk_level=RiskLevel.YELLOW,
                deviation_summary="The confidentiality protection may be weaker than the ACTA baseline.",
                suggested_action="Use clearer confidentiality obligations and standard ACTA exceptions.",
                confidence=0.83,
                rationale="The clause allows discretionary use of confidential information.",
            )
        ],
    )

    class FakeResponse:
        content = """
        {
          "suggestions": [
            {
              "clause_id": "clause-1",
              "original_text": "Recipient may use confidential information as it deems appropriate.",
              "suggested_text": "Recipient shall protect confidential information using at least the same degree of care it uses for its own confidential information and may use it only for study-related purposes.",
              "reason": "Tightens use restrictions and restores a more standard confidentiality protection.",
              "priority": "medium"
            }
          ]
        }
        """

    class FakeLLM:
        def invoke(self, messages):
            assert len(messages) == 2
            return FakeResponse()

    agent = SuggestionAgent()
    agent.llm = FakeLLM()

    result = agent(state)

    assert len(result["suggestions"]) == 1
    assert result["suggestions"][0].suggested_text.startswith("Recipient shall protect confidential information")
    assert result["suggestions"][0].priority == "medium"
    assert "clause-1 (original)" in result["version_diff"]


def test_suggestion_agent_falls_back_and_adds_missing_clause_suggestions() -> None:
    state = ContractReviewState(
        review_id="review-fallback",
        raw_text="Test contract",
        risk_findings=[
            RiskFinding(
                clause_id="clause-2",
                clause_type=ClauseType.PAYMENT_TERMS,
                clause_text="Invoices are due within ninety days.",
                risk_level=RiskLevel.YELLOW,
                deviation_summary="The payment timing is slower than ACTA's net-30 style baseline.",
                suggested_action="Restore net-30 timing and tie payment to itemized invoicing.",
                confidence=0.76,
                rationale="Net 90 timing creates cash-flow drag.",
            )
        ],
        compliance_findings=[
            ComplianceFinding(
                clause_type="Termination",
                status="missing",
                detail="Missing expected CTA section: Termination.",
            )
        ],
    )

    class FailingLLM:
        def invoke(self, messages):
            raise RuntimeError("LLM unavailable")

    agent = SuggestionAgent()
    agent.llm = FailingLLM()

    result = agent(state)

    assert len(result["suggestions"]) == 2
    assert result["suggestions"][0].priority == "high"
    assert any(s.clause_id == "missing:termination" for s in result["suggestions"])
    assert "+ [Missing Clause] Add a Termination clause" in result["version_diff"]
