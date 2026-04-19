from __future__ import annotations

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    title: str = Field(min_length=1)
    filename: str = "inline.txt"
    text: str = Field(min_length=1)


class ReviewRequest(BaseModel):
    text: str = Field(min_length=1)
    title: str = "Contract Review"
    with_human_review: bool = False


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    context: str = ""


class ChatResponse(BaseModel):
    answer: str


class AssessmentPayload(BaseModel):
    clause_type: str
    raw_text: str
    risk_level: str
    deviation_summary: str
    suggested_action: str
    confidence: float


class RedlinePayload(BaseModel):
    proposed_text: str
    original_text: str = ""
    suggested_text: str = ""
    reason: str = ""
    priority: str = "medium"


class SuggestionPayload(BaseModel):
    clause_id: str
    clause_type: str
    original_text: str = ""
    suggested_text: str = ""
    reason: str = ""
    priority: str = "medium"
    confidence: float


class ClausePayload(BaseModel):
    assessment: AssessmentPayload
    redline: RedlinePayload | None = None
    model_used: str | None = None


class AnalyzeResponse(BaseModel):
    summary: str
    clauses: list[ClausePayload]
    suggestions: list[SuggestionPayload] = Field(default_factory=list)
    missing_clause_types: list[str] = Field(default_factory=list)
    extraction_model: str | None = None
    version_diff: str = ""
    risk_score: int = 0


class ActaRewriteClause(BaseModel):
    type: str | None = None
    text: str = Field(min_length=1)
    risk_reason: str | None = None
    suggested_clause: str | None = None
    deviation: str | None = None


class ActaRewriteRequest(BaseModel):
    clauses: dict[str, ActaRewriteClause] = Field(default_factory=dict)


class ActaRewriteResponse(BaseModel):
    rewrites: dict[str, str] = Field(default_factory=dict)
