from __future__ import annotations

from langgraph.graph import END, StateGraph

from src.agents.clause_extraction import ClauseExtractionAgent
from src.agents.compliance_check import ComplianceCheckAgent
from src.agents.risk_identification import RiskIdentificationAgent
from src.agents.suggestion import SuggestionAgent
from src.pipeline.state import ContractReviewState


def create_review_pipeline():
    graph = StateGraph(ContractReviewState)

    graph.add_node("clause_extraction", ClauseExtractionAgent())
    graph.add_node("risk_identification", RiskIdentificationAgent())
    graph.add_node("compliance_check", ComplianceCheckAgent())
    graph.add_node("suggestion", SuggestionAgent())

    graph.set_entry_point("clause_extraction")
    graph.add_edge("clause_extraction", "risk_identification")
    graph.add_edge("risk_identification", "compliance_check")
    graph.add_edge("compliance_check", "suggestion")
    graph.add_edge("suggestion", END)

    return graph.compile()
