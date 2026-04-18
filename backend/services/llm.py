"""
ACTA AI — Complete LLM Integration Layer
=========================================

WHERE EACH API IS USED:
─────────────────────────────────────────────────────────────────
GEMINI 2.0 FLASH  →  Fast, cost-efficient tasks:
  • Clause classification (what type is this clause?)
  • Document summarization (executive summary generation)
  • General chat Q&A about contract content
  • Quick compliance checks on low-risk clauses

K2 (Legal Reasoning Model)  →  Heavy legal analysis:
  • Indemnification clause deep analysis
  • Intellectual Property ownership disputes
  • Publication rights ACTA comparison
  • High-confidence redline generation
  • Any clause flagged CRITICAL by Gemini (second-pass verification)
─────────────────────────────────────────────────────────────────
"""

from flask.cli import load_dotenv
import requests
import json
import os
from pathlib import Path

load_dotenv() 
GEMINI_MODEL = "gemini-2.0-flash"
K2_API_BASE = "https://api.k2.ai/v1"   # update to real K2 endpoint when confirmed

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def load_local_env() -> None:
    """
    Loads simple KEY=VALUE pairs from the repo-level .env file.
    Existing environment variables win so shell exports still override local defaults.
    """
    if not ENV_FILE.exists():
        return

    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


def get_gemini_key(override: str = "") -> str:
    load_local_env()
    return override or os.getenv("GEMINI_API_KEY", "")


def get_k2_key() -> str:
    load_local_env()
    return os.getenv("K2_API_KEY", "")


# ══════════════════════════════════════════════════════════════
# GEMINI — CORE CALL
# USE FOR: classification, summarization, chat, fast analysis
# ══════════════════════════════════════════════════════════════
<<<<<<< HEAD
def call_gemini(GEMINI_API_KEY: str, prompt: str, temperature: float = 0.2) -> str | None:
    key = GEMINI_API_KEY or GEMINI_KEY
=======
def call_gemini(api_key: str, prompt: str, temperature: float = 0.2) -> str | None:
    key = get_gemini_key(api_key)
>>>>>>> d0334c75795e5796eb5bb3b9228f410d81195343
    if not key:
        print("⚠️  No Gemini API key provided")
        return None

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={key}"

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": 1200
        }
    }

    try:
        res = requests.post(url, json=payload, timeout=30)
        res.raise_for_status()
        data = res.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"❌ Gemini error: {e}")
        return None


# ══════════════════════════════════════════════════════════════
# K2 — LEGAL REASONING CALL
# USE FOR: indemnification, IP, publication rights, critical clauses
# K2 is routed here via orchestrator when clause type requires
# deep legal reasoning beyond Gemini's capability
# ══════════════════════════════════════════════════════════════
def call_k2(prompt: str, system_prompt: str = None) -> str | None:
    k2_key = get_k2_key()
    if not k2_key:
        print("⚠️  K2_API_KEY not set — falling back to Gemini")
        return None

    headers = {
        "Authorization": f"Bearer {k2_key}",
        "Content-Type": "application/json"
    }

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": "k2-legal",      # K2's legal-specialized model
        "messages": messages,
        "temperature": 0.1,       # Very low — we want deterministic legal output
        "max_tokens": 2000
    }

    try:
        res = requests.post(
            f"{K2_API_BASE}/chat/completions",
            headers=headers,
            json=payload,
            timeout=45
        )
        res.raise_for_status()
        data = res.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"❌ K2 error: {e}")
        return None


# ══════════════════════════════════════════════════════════════
# SMART ROUTER
# Decides Gemini vs K2 based on clause type and deviation
# ══════════════════════════════════════════════════════════════
LEGAL_HEAVY_TYPES = {
    "Indemnification",
    "Intellectual Property",
    "Publication Rights",
    "Governing Law",
}

def route_llm(clause_type: str, prompt: str, GEMINI_API_KEY: str = "") -> tuple[str | None, str]:
    """
    Returns (response_text, model_used)
    Routes to K2 for legal-heavy clauses, Gemini otherwise.
    Falls back to Gemini if K2 is unavailable.
    """
    use_k2 = clause_type in LEGAL_HEAVY_TYPES

    if use_k2:
        k2_system = """You are a senior clinical trial legal expert with 20 years of experience 
        negotiating Clinical Trial Agreements. You specialize in ACTA compliance.
        You identify deviations with surgical precision and generate legally sound redlines."""

        result = call_k2(prompt, system_prompt=k2_system)
        if result:
            return result, "K2"

        print(f"⚠️  K2 failed for {clause_type} — falling back to Gemini")

    result = call_gemini(GEMINI_API_KEY, prompt)
    return result, "Gemini"


# ══════════════════════════════════════════════════════════════
# JSON PARSER (handles Gemini markdown wrapping)
# ══════════════════════════════════════════════════════════════
def safe_parse_json(text: str) -> dict | None:
    if not text:
        return None
    try:
        cleaned = text.replace("```json", "").replace("```", "").strip()
        return json.loads(cleaned)
    except Exception as e:
        print(f"❌ JSON parse error: {e}")
        return None


# ══════════════════════════════════════════════════════════════
# STEP 1: CLAUSE CLASSIFICATION
# USES: Gemini (fast, cheap — just categorizing text)
# Called by: clause_splitter.py
# ══════════════════════════════════════════════════════════════
def classify_clause_with_gemini(GEMINI_API_KEY: str, clause_text: str) -> str:
    """
    Uses Gemini to classify raw clause text into ACTA categories.
    Returns one of: Confidentiality | Indemnification | Payment Terms |
    Intellectual Property | Publication Rights | Termination | Governing Law | General Clause
    """
    prompt = f"""
You are a clinical trial legal classifier.

Classify the following clause into EXACTLY ONE of these categories:
- Confidentiality
- Indemnification
- Payment Terms
- Intellectual Property
- Publication Rights
- Termination
- Governing Law
- General Clause

Return ONLY the category name. No explanation.

CLAUSE:
{clause_text[:800]}
"""
    result = call_gemini(GEMINI_API_KEY, prompt, temperature=0.0)
    if result:
        result = result.strip()
        valid = {"Confidentiality", "Indemnification", "Payment Terms",
                 "Intellectual Property", "Publication Rights",
                 "Termination", "Governing Law", "General Clause"}
        return result if result in valid else "General Clause"
    return "General Clause"


# ══════════════════════════════════════════════════════════════
# STEP 2: ACTA COMPLIANCE ANALYSIS
# USES: K2 for legal-heavy types, Gemini for others
# Called by: analyze.py for each clause
# ══════════════════════════════════════════════════════════════
def build_acta_prompt(clause_name: str, clause_type: str, clause_text: str) -> str:
    """
    Builds the ACTA compliance prompt. The same prompt structure
    is used for both Gemini and K2 — the router decides which model runs it.
    """
    return f"""
You are a senior clinical trial legal AI. Analyze this clause for ACTA compliance.

ACTA STANDARDS (what compliant looks like):
- Publication Rights: Site gets 60-day review period. Sponsor may delay up to 90 days for patent filing only.
- Intellectual Property: Sponsor retains all rights to investigational compound and its derivatives. Site retains rights to independently developed IP.
- Indemnification: Mutual negligence-based only. No blanket indemnification. Sponsor indemnifies for product liability.
- Confidentiality: 5-year protection standard. Excludes publicly known information.
- Payment Terms: Net-30 invoice payment. Itemized budget with indirect cost cap at 26% F&A.
- Protocol Deviations: Must be reported to sponsor within 5 business days.
- Subject Injury: Sponsor covers costs for research-related injuries. Site not liable for standard of care costs.

CLAUSE TYPE: {clause_type}
CLAUSE NAME: {clause_name}

CLAUSE TEXT:
{clause_text}

Return ONLY valid JSON (no markdown, no explanation):
{{
  "deviation": "critical | minor | aligned",
  "risk_reason": "1-2 sentence legal explanation of what deviates and why it matters",
  "suggested_clause": "Full ACTA-compliant replacement clause text",
  "confidence": 0.0
}}

deviation rules:
- critical = directly contradicts ACTA standards or creates major legal exposure
- minor = suboptimal but not catastrophic; standard negotiation point
- aligned = matches ACTA standards
"""


def analyze_clause_with_ai(GEMINI_API_KEY: str, clause_name: str, clause_text: str, clause_type: str = "General Clause") -> dict:
    """
    Main analysis function. Routes to K2 or Gemini based on clause type.
    Returns structured dict with deviation, risk_reason, suggested_clause, confidence, model_used.
    """
    prompt = build_acta_prompt(clause_name, clause_type, clause_text)

    response, model_used = route_llm(clause_type, prompt, GEMINI_API_KEY)

    parsed = safe_parse_json(response)

    if not parsed:
        return {
            "deviation": "minor",
            "risk_reason": f"AI ({model_used}) unavailable or response unparseable.",
            "suggested_clause": clause_text,
            "confidence": 0.0,
            "model_used": model_used
        }

    parsed.setdefault("confidence", 0.75)
    parsed["model_used"] = model_used
    return parsed


# ══════════════════════════════════════════════════════════════
# STEP 3: EXECUTIVE SUMMARY GENERATION
# USES: Gemini (summarization — this is Gemini's strength)
# Called by: analyze.py after all clauses processed
# ══════════════════════════════════════════════════════════════
def generate_executive_summary(GEMINI_API_KEY: str, metrics: dict, critical_clauses: list[str]) -> str:
    """
    Uses Gemini to generate a human-readable executive summary
    of the full contract analysis for the dashboard.
    """
    prompt = f"""
You are a senior legal advisor summarizing a Clinical Trial Agreement analysis.

ANALYSIS RESULTS:
- Risk Level: {metrics.get('risk_level', 'UNKNOWN')}
- Total Clauses Analyzed: {metrics.get('total_clauses', 0)}
- Critical Deviations: {metrics.get('critical', 0)}
- Minor Deviations: {metrics.get('minor', 0)}  
- ACTA-Aligned Clauses: {metrics.get('aligned', 0)}
- Critical Clause Types: {', '.join(critical_clauses) if critical_clauses else 'None'}

Write a 3-sentence executive summary for a clinical trial manager (non-lawyer).
- Sentence 1: Overall risk assessment
- Sentence 2: Biggest specific concern  
- Sentence 3: Clear recommendation
Be direct. No jargon. No bullet points.
"""
    result = call_gemini(GEMINI_API_KEY, prompt, temperature=0.3)
    return result or metrics.get("recommendation", "Analysis complete.")


# ══════════════════════════════════════════════════════════════
# STEP 4: CHAT / Q&A
# USES: Gemini (conversational — fast responses)
# Called by: chat.py route
# ══════════════════════════════════════════════════════════════
def answer_contract_question(GEMINI_API_KEY: str, question: str, context: str) -> str:
    """
    Uses Gemini for interactive Q&A about the contract.
    Context = full contract text or selected clause.
    """
    prompt = f"""
You are ACTA AI, a senior clinical trial legal expert.

Your job is to help clinical trial managers and site lawyers understand and negotiate CTAs.

RULES:
- Give legally accurate, specific answers
- Identify risks clearly with ACTA standard reference
- Suggest improvements when relevant
- Be concise but precise (3-5 sentences max unless more is needed)
- If unsure, say so explicitly

CONTRACT CONTEXT:
{context[:3000]}

USER QUESTION:
{question}

FORMAT:
- Direct answer first
- Risk or ACTA deviation explanation (if applicable)
- Negotiation suggestion (if applicable)
"""
<<<<<<< HEAD
    result = call_gemini(GEMINI_API_KEY, prompt, temperature=0.3)
    return result or "Unable to generate a response. Please try again."
=======
    result = call_gemini(api_key, prompt, temperature=0.3)
    return result or "Unable to generate a response. Please try again."
>>>>>>> d0334c75795e5796eb5bb3b9228f410d81195343
