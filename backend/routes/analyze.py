from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from backend.services.clause_splitter import split_into_clauses
from backend.services.redline import generate_redlines
from backend.services.llm import (
    analyze_clause_with_ai,
    classify_clause_with_gemini,
    generate_executive_summary
)

router = APIRouter()


class CTARequest(BaseModel):
    filename: str
    text: str
    gemini_key: Optional[str] = None


@router.post("/analyze")
def analyze_cta(req: CTARequest):

    # ── STEP 1: Split into sentence blocks ──────────────────────────
    raw_clauses = split_into_clauses(req.text)

    if not raw_clauses:
        return {
            "filename": req.filename,
            "summary": "No clauses could be extracted from this document.",
            "metrics": {"critical": 0, "minor": 0, "aligned": 0, "risk_level": "LOW", "total_clauses": 0},
            "clauses": {},
            "redlines": []
        }

    analyzed = {}

    # ── STEP 2: Per-clause analysis (Gemini classifies, K2/Gemini analyzes) ──
    for i, clause in enumerate(raw_clauses[:15]):

        clause_text = clause.get("text", "") if isinstance(clause, dict) else str(clause)

        # Gemini classifies the clause type first (fast + cheap)
        clause_type = classify_clause_with_gemini(req.gemini_key, clause_text)

        clause_key = f"{clause_type} #{i+1}"

        # Router picks K2 or Gemini based on clause_type
        ai_result = analyze_clause_with_ai(
            req.gemini_key,
            clause_key,
            clause_text,
            clause_type=clause_type
        )

        analyzed[clause_key] = {
            "type": clause_type,
            "text": clause_text,
            "deviation": ai_result.get("deviation", "minor"),
            "risk_reason": ai_result.get("risk_reason", ""),
            "suggested_clause": ai_result.get("suggested_clause", clause_text),
            "confidence": ai_result.get("confidence", 0.0),
            "model_used": ai_result.get("model_used", "Gemini"),
        }

    # ── STEP 3: Aggregate metrics ────────────────────────────────────
    critical = sum(1 for c in analyzed.values() if c["deviation"] == "critical")
    minor    = sum(1 for c in analyzed.values() if c["deviation"] == "minor")
    aligned  = sum(1 for c in analyzed.values() if c["deviation"] == "aligned")

    risk_level = "HIGH" if critical >= 3 else "MEDIUM" if critical >= 1 else "LOW"

    metrics = {
        "risk_level": risk_level,
        "total_clauses": len(analyzed),
        "critical": critical,
        "minor": minor,
        "aligned": aligned,
        "recommendation": (
            "Immediate legal review required — critical ACTA deviations detected."
            if risk_level == "HIGH" else
            "Legal review recommended before execution."
            if risk_level == "MEDIUM" else
            "Document is generally compliant with ACTA standards."
        )
    }

    # ── STEP 4: Executive summary via Gemini ─────────────────────────
    critical_types = [v["type"] for v in analyzed.values() if v["deviation"] == "critical"]
    summary = generate_executive_summary(req.gemini_key, metrics, critical_types)

    # ── STEP 5: Generate redlines ────────────────────────────────────
    redlines = generate_redlines(analyzed)

    return {
        "filename": req.filename,
        "summary": summary,
        "clauses": analyzed,
        "metrics": metrics,
        "redlines": redlines,
    }