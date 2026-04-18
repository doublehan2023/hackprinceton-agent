from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ClauseType(str, Enum):
    CONFIDENTIALITY = "Confidentiality"
    INDEMNIFICATION = "Indemnification"
    PAYMENT_TERMS = "Payment Terms"
    INTELLECTUAL_PROPERTY = "Intellectual Property"
    PUBLICATION_RIGHTS = "Publication Rights"
    TERMINATION = "Termination"
    GOVERNING_LAW = "Governing Law"
    SUBJECT_INJURY = "Subject Injury"
    PROTOCOL_DEVIATIONS = "Protocol Deviations"
    GENERAL = "General Clause"


class RiskLevel(str, Enum):
    RED = "red"
    YELLOW = "yellow"
    GREEN = "green"


class Clause(BaseModel):
    id: str
    clause_type: ClauseType
    text: str
    source_order: int
    section_title: str | None = None
    section_order: int | None = None
    evidence: list[str] = Field(default_factory=list)
    classification_confidence: float = Field(ge=0.0, le=1.0)


class RiskFinding(BaseModel):
    clause_id: str
    clause_type: ClauseType
    clause_text: str
    risk_level: RiskLevel
    deviation_summary: str
    suggested_action: str
    confidence: float = Field(ge=0.0, le=1.0)
    needs_human_review: bool = False
    matched_terms: list[str] = Field(default_factory=list)
    missing_terms: list[str] = Field(default_factory=list)


class ComplianceFinding(BaseModel):
    clause_type: str
    status: str
    detail: str


class Suggestion(BaseModel):
    clause_id: str
    clause_type: ClauseType
    proposed_text: str
    rationale: str
    confidence: float = Field(ge=0.0, le=1.0)


class Section(BaseModel):
    title: str | None = None
    body: str
    source_order: int
    heading_level: int | None = Field(default=None, ge=1)


class ContractReviewState(BaseModel):
    review_id: str
    filename: str = "inline.txt"
    raw_text: str
    sections: list[Section] = Field(default_factory=list)
    clauses: list[Clause] = Field(default_factory=list)
    risk_findings: list[RiskFinding] = Field(default_factory=list)
    compliance_findings: list[ComplianceFinding] = Field(default_factory=list)
    suggestions: list[Suggestion] = Field(default_factory=list)
    missing_clause_types: list[str] = Field(default_factory=list)
    needs_human_review: bool = False
    summary: str = ""
