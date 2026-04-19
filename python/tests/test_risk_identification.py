from __future__ import annotations

from src.agents.risk_identification import RiskIdentificationAgent
from src.pipeline.state import Clause, ClauseType, ContractReviewState, RiskLevel


def test_risk_identification_escalates_acta_deviation_rules() -> None:
    state = ContractReviewState(
        review_id="risk-rules",
        raw_text="Termination clause",
        clauses=[
            Clause(
                id="clause-1",
                clause_type=ClauseType.TERMINATION,
                text="Sponsor may terminate this agreement at any time in its sole discretion without cause.",
                source_order=1,
                classification_confidence=0.91,
            )
        ],
    )

    result = RiskIdentificationAgent()(state)

    assert result["overall_risk_level"] is RiskLevel.RED
    assert result["risk_findings"][0].risk_type == "unilateral_termination"
    assert result["risk_findings"][0].risk_level is RiskLevel.RED
    assert result["risk_findings"][0].engine == "rules"
    assert result["needs_human_review"] is True


def test_risk_identification_merges_llm_assessment_with_rule_baseline() -> None:
    state = ContractReviewState(
        review_id="risk-llm",
        raw_text="Publication clause",
        clauses=[
            Clause(
                id="clause-1",
                clause_type=ClauseType.PUBLICATION_RIGHTS,
                text="Site must obtain sponsor's prior written consent before any publication.",
                source_order=1,
                classification_confidence=0.8,
            )
        ],
    )

    class FakeResponse:
        content = """
        {
          "findings": [
            {
              "clause_id": "clause-1",
              "risk_level": "red",
              "risk_type": "publication_veto",
              "description": "The clause gives the sponsor an approval right that exceeds the ACTA review period.",
              "buyer_impact": "The site can lose meaningful publication control.",
              "seller_impact": "The sponsor gains leverage to delay or block publication.",
              "rationale": "ACTA permits limited review and patent delay, not open-ended approval rights.",
              "suggested_action": "Replace approval rights with a short review window.",
              "confidence": 0.93
            }
          ],
          "overall_risk_level": "red",
          "risk_summary": "Publication rights materially deviate from ACTA."
        }
        """

    class FakeLLM:
        def invoke(self, messages):
            assert len(messages) == 2
            return FakeResponse()

    agent = RiskIdentificationAgent()
    agent.llm = FakeLLM()
    agent.analysis_model = "llm"

    result = agent(state)
    finding = result["risk_findings"][0]

    assert result["overall_risk_level"] is RiskLevel.RED
    assert finding.risk_level is RiskLevel.RED
    assert finding.risk_type == "publication_veto"
    assert finding.engine == "merged"
    assert "publication control" in finding.buyer_impact
    assert result["risk_summary"].startswith("Reviewed 1 clauses.")


def test_risk_identification_marks_results_provisional_when_k2_fails() -> None:
    state = ContractReviewState(
        review_id="risk-fallback",
        raw_text="Payment clause",
        clauses=[
            Clause(
                id="clause-1",
                clause_type=ClauseType.PAYMENT_TERMS,
                text="Invoices will be paid within net 90 days after receipt.",
                source_order=1,
                classification_confidence=0.78,
            )
        ],
    )

    class BrokenLLM:
        def invoke(self, messages):
            raise RuntimeError("boom")

    agent = RiskIdentificationAgent()
    agent.llm = BrokenLLM()
    agent.analysis_model = "llm"

    result = agent(state)
    finding = result["risk_findings"][0]

    assert result["overall_risk_level"] is RiskLevel.YELLOW
    assert finding.risk_type == "extended_payment_timeline"
    assert finding.engine == "rules"
    assert result["needs_human_review"] is True
    assert result["errors"] == ["Risk identification K2 analysis failed: boom"]
    assert "K2 analysis is required" in result["risk_summary"]


def test_risk_identification_requires_k2_provider(monkeypatch) -> None:
    state = ContractReviewState(
        review_id="risk-requires-k2",
        raw_text="Payment clause",
        clauses=[
            Clause(
                id="clause-1",
                clause_type=ClauseType.PAYMENT_TERMS,
                text="Invoices will be paid within net 90 days after receipt.",
                source_order=1,
                classification_confidence=0.78,
            )
        ],
    )

    class FakeSettings:
        llm_provider = "llm"

    monkeypatch.setattr("src.agents.risk_identification.get_settings", lambda: FakeSettings())

    result = RiskIdentificationAgent()(state)

    assert result["needs_human_review"] is True
    assert result["errors"] == ["Risk identification requires K2. Set K2_API_KEY to enable K2 analysis."]
    assert "K2 analysis is required" in result["summary"]
