from __future__ import annotations

import asyncio

from src.api.main import ActaRewriteRequest, acta_rewrite


def test_acta_rewrite_prefers_existing_suggested_clause() -> None:
    response = asyncio.run(
        acta_rewrite(
            ActaRewriteRequest(
                clauses={
                    "Clause 1: Confidentiality": {
                        "type": "Confidentiality",
                        "text": "Weak confidentiality text.",
                        "suggested_clause": "Tightened confidentiality language.",
                    }
                }
            )
        )
    )

    assert response.rewrites["Clause 1: Confidentiality"] == "Tightened confidentiality language."


def test_acta_rewrite_falls_back_to_playbook_language() -> None:
    response = asyncio.run(
        acta_rewrite(
            ActaRewriteRequest(
                clauses={
                    "Clause 2: Payment Terms": {
                        "type": "Payment Terms",
                        "text": "Invoices are due in ninety days.",
                    }
                }
            )
        )
    )

    assert "net 30" in response.rewrites["Clause 2: Payment Terms"].lower()
