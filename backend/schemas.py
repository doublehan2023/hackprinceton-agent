from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class NegotiationStatus(str, Enum):
    draft = "draft"
    review = "review"
    agreed = "agreed"


class RiskLevel(str, Enum):
    red = "red"
    yellow = "yellow"
    green = "green"


class RedlineStatus(str, Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"


class AnnotationType(str, Enum):
    risk = "risk"
    redline = "redline"
    missed = "missed"


class ClauseType(str, Enum):
    confidentiality = "Confidentiality"
    indemnification = "Indemnification"
    payment_terms = "Payment Terms"
    intellectual_property = "Intellectual Property"
    publication_rights = "Publication Rights"
    termination = "Termination"
    governing_law = "Governing Law"
    subject_injury = "Subject Injury"
    protocol_deviations = "Protocol Deviations"
    general = "General Clause"


class AnalyzeRequest(BaseModel):
    negotiation_id: str | None = None
    title: str = Field(..., min_length=1)
    sponsor: str | None = None
    site: str | None = None
    pen_holder: str | None = None
    uploaded_by: str | None = None
    filename: str = Field(default="inline.txt")
    text: str = Field(..., min_length=1)


class ClassifiedClause(BaseModel):
    clause_type: ClauseType
    raw_text: str
    source_order: int
    classification_confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)


class ClauseMap(BaseModel):
    clauses: list[ClassifiedClause]
    missing_clause_types: list[ClauseType] = Field(default_factory=list)


class ReasoningTrace(BaseModel):
    acta_standard_excerpt: str
    deviation_detected: str
    why_it_matters: str
    confidence_factors: list[str] = Field(default_factory=list)


class ClauseAssessment(BaseModel):
    clause_type: ClauseType
    raw_text: str
    risk_level: RiskLevel
    risk_score: float = Field(ge=0.0, le=1.0)
    deviation_summary: str
    suggested_action: str
    reasoning_trace: ReasoningTrace
    confidence: float = Field(ge=0.0, le=1.0)
    critic_notes: list[str] = Field(default_factory=list)
    human_review_required: bool = False


class RedlineDraft(BaseModel):
    clause_type: ClauseType
    original_text: str
    proposed_text: str
    rationale: str
    confidence: float = Field(ge=0.0, le=1.0)
    source: Literal["acta_baseline", "agent"] = "acta_baseline"


class ClauseResult(BaseModel):
    id: str
    assessment: ClauseAssessment
    redline: RedlineDraft | None = None


class AnalyzeResponse(BaseModel):
    negotiation_id: str
    version_id: str
    version_number: int
    summary: str
    missing_clause_types: list[ClauseType]
    clauses: list[ClauseResult]
    generated_at: datetime


class VersionSummary(BaseModel):
    id: str
    negotiation_id: str
    version_number: int
    uploaded_by: str | None
    filename: str | None
    created_at: datetime


class AnnotationCreate(BaseModel):
    clause_id: str | None = None
    redline_id: str | None = None
    annotation_type: AnnotationType
    agent_risk_level: RiskLevel | None = None
    human_risk_level: RiskLevel | None = None
    correction_reasoning: str = Field(..., min_length=1)
    was_corrected: bool = True
    confidence_rating: float | None = Field(default=None, ge=0.0, le=1.0)
    clause_type: ClauseType | None = None
    prompt: str | None = None
    completion: str | None = None


class AnnotationResponse(BaseModel):
    annotation_id: str
    training_example_id: str | None = None
