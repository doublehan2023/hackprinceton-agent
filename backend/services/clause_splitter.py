import re

# -----------------------------
# LEGAL CLAUSE MAP
# -----------------------------
CLAUSE_MAP = {
    "Confidentiality": [
        "confidential", "non-disclosure", "proprietary"
    ],
    "Indemnification": [
        "indemnify", "hold harmless", "liability"
    ],
    "Payment Terms": [
        "payment", "invoice", "fees", "compensation"
    ],
    "Intellectual Property": [
        "intellectual property", "ownership", "patent", "invention"
    ],
    "Publication Rights": [
        "publication", "publish", "journal"
    ],
    "Termination": [
        "terminate", "termination", "end of agreement"
    ],
    "Governing Law": [
        "governing law", "jurisdiction", "court"
    ]
}


# -----------------------------
# CLEAN TEXT
# -----------------------------
def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# -----------------------------
# SPLIT INTO SENTENCE BLOCKS
# -----------------------------
def split_blocks(text: str):
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if len(s.strip()) > 30]


# -----------------------------
# CLAUSE DETECTION CORE
# -----------------------------
def detect_clause_type(text: str) -> str:
    text_lower = text.lower()

    best_match = "General Clause"
    best_score = 0

    for clause_type, keywords in CLAUSE_MAP.items():
        score = sum(1 for k in keywords if k in text_lower)

        if score > best_score:
            best_score = score
            best_match = clause_type

    return best_match


# -----------------------------
# MAIN FUNCTION
# -----------------------------
def split_into_clauses(text: str):
    text = clean_text(text)
    blocks = split_blocks(text)

    clauses = []

    for block in blocks:
        clause_type = detect_clause_type(block)

        clauses.append({
            "clause_type": clause_type,
            "text": block
        })

    return clauses