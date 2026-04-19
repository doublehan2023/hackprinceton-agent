from __future__ import annotations

from src.pipeline.state import ClauseType, RiskLevel
from src.rules.engine import ACTA_RISK_RULES, PLAYBOOK, RULESET_VERSION


def test_ruleset_loads_from_versioned_data_files() -> None:
    assert RULESET_VERSION == "v1"
    assert PLAYBOOK[ClauseType.CONFIDENTIALITY]["required_terms"] == [
        "five years",
        "publicly known",
        "independently developed",
    ]
    assert "net 30" in PLAYBOOK[ClauseType.PAYMENT_TERMS]["standard_text"].lower()


def test_risk_rules_load_with_enum_levels() -> None:
    payment_rules = ACTA_RISK_RULES[ClauseType.PAYMENT_TERMS]

    assert payment_rules[0]["name"] == "extended_payment_timeline"
    assert payment_rules[0]["risk_level"] is RiskLevel.YELLOW
    assert "net 90" in payment_rules[0]["patterns"]
