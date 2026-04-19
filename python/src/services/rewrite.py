from __future__ import annotations

from src.api.schemas import ActaRewriteRequest, ActaRewriteResponse
from src.pipeline.state import ClauseType
from src.rules.engine import PLAYBOOK


def coerce_clause_type(raw_type: str | None) -> ClauseType | None:
    if not raw_type:
        return None

    normalized = raw_type.strip().lower()
    for clause_type in ClauseType:
        if clause_type.value.lower() == normalized:
            return clause_type
    return None


def rewrite_to_acta(payload: ActaRewriteRequest) -> ActaRewriteResponse:
    rewrites: dict[str, str] = {}

    for key, clause in payload.clauses.items():
        if clause.suggested_clause and clause.suggested_clause.strip():
            rewrites[key] = clause.suggested_clause.strip()
            continue

        clause_type = coerce_clause_type(clause.type)
        if clause_type is not None:
            rewrites[key] = str(PLAYBOOK[clause_type]["standard_text"])
            continue

        rewrites[key] = clause.text.strip()

    return ActaRewriteResponse(rewrites=rewrites)
