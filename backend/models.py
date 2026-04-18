SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS negotiation (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        sponsor TEXT,
        site TEXT,
        pen_holder TEXT,
        status TEXT NOT NULL DEFAULT 'draft',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS version (
        id TEXT PRIMARY KEY,
        negotiation_id TEXT NOT NULL,
        version_number INTEGER NOT NULL,
        uploaded_by TEXT,
        filename TEXT,
        raw_text TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (negotiation_id) REFERENCES negotiation(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS clause (
        id TEXT PRIMARY KEY,
        version_id TEXT NOT NULL,
        clause_type TEXT NOT NULL,
        raw_text TEXT NOT NULL,
        classification_confidence REAL NOT NULL,
        risk_level TEXT NOT NULL,
        risk_score REAL NOT NULL,
        deviation_summary TEXT NOT NULL,
        reasoning_trace TEXT NOT NULL,
        suggested_action TEXT NOT NULL,
        confidence REAL NOT NULL,
        human_review_required INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY (version_id) REFERENCES version(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS redline (
        id TEXT PRIMARY KEY,
        clause_id TEXT NOT NULL,
        original_text TEXT NOT NULL,
        proposed_text TEXT NOT NULL,
        rationale TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        resolved_by TEXT,
        confidence REAL NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (clause_id) REFERENCES clause(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS annotation (
        id TEXT PRIMARY KEY,
        clause_id TEXT,
        redline_id TEXT,
        annotation_type TEXT NOT NULL,
        agent_risk_level TEXT,
        human_risk_level TEXT,
        correction_reasoning TEXT NOT NULL,
        was_corrected INTEGER NOT NULL DEFAULT 1,
        confidence_rating REAL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (clause_id) REFERENCES clause(id),
        FOREIGN KEY (redline_id) REFERENCES redline(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS training_example (
        id TEXT PRIMARY KEY,
        annotation_id TEXT NOT NULL,
        clause_type TEXT,
        prompt TEXT NOT NULL,
        completion TEXT NOT NULL,
        split TEXT NOT NULL DEFAULT 'train',
        exported INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY (annotation_id) REFERENCES annotation(id)
    )
    """,
]
