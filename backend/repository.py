from datetime import datetime, UTC
import json
import uuid

from backend.db import db_session
from backend.schemas import AnnotationCreate, ClauseAssessment, RedlineDraft, VersionSummary


def _now() -> str:
    return datetime.now(UTC).isoformat()


def create_negotiation(title: str, sponsor: str | None, site: str | None, pen_holder: str | None) -> str:
    negotiation_id = str(uuid.uuid4())
    now = _now()
    with db_session() as connection:
        connection.execute(
            """
            INSERT INTO negotiation (id, title, sponsor, site, pen_holder, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'draft', ?, ?)
            """,
            (negotiation_id, title, sponsor, site, pen_holder, now, now),
        )
    return negotiation_id


def get_next_version_number(negotiation_id: str) -> int:
    with db_session() as connection:
        row = connection.execute(
            "SELECT COALESCE(MAX(version_number), 0) + 1 AS next_version FROM version WHERE negotiation_id = ?",
            (negotiation_id,),
        ).fetchone()
    return int(row["next_version"])


def create_version(
    negotiation_id: str,
    version_number: int,
    uploaded_by: str | None,
    filename: str | None,
    raw_text: str,
) -> str:
    version_id = str(uuid.uuid4())
    with db_session() as connection:
        connection.execute(
            """
            INSERT INTO version (id, negotiation_id, version_number, uploaded_by, filename, raw_text, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (version_id, negotiation_id, version_number, uploaded_by, filename, raw_text, _now()),
        )
        connection.execute(
            "UPDATE negotiation SET updated_at = ? WHERE id = ?",
            (_now(), negotiation_id),
        )
    return version_id


def create_clause(version_id: str, assessment: ClauseAssessment, classification_confidence: float) -> str:
    clause_id = str(uuid.uuid4())
    with db_session() as connection:
        connection.execute(
            """
            INSERT INTO clause (
                id, version_id, clause_type, raw_text, classification_confidence, risk_level, risk_score,
                deviation_summary, reasoning_trace, suggested_action, confidence, human_review_required, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                clause_id,
                version_id,
                assessment.clause_type.value,
                assessment.raw_text,
                classification_confidence,
                assessment.risk_level.value,
                assessment.risk_score,
                assessment.deviation_summary,
                json.dumps(assessment.reasoning_trace.model_dump()),
                assessment.suggested_action,
                assessment.confidence,
                1 if assessment.human_review_required else 0,
                _now(),
            ),
        )
    return clause_id


def create_redline(clause_id: str, draft: RedlineDraft) -> str:
    redline_id = str(uuid.uuid4())
    with db_session() as connection:
        connection.execute(
            """
            INSERT INTO redline (
                id, clause_id, original_text, proposed_text, rationale, status, resolved_by, confidence, created_at
            )
            VALUES (?, ?, ?, ?, ?, 'pending', NULL, ?, ?)
            """,
            (
                redline_id,
                clause_id,
                draft.original_text,
                draft.proposed_text,
                draft.rationale,
                draft.confidence,
                _now(),
            ),
        )
    return redline_id


def list_versions(negotiation_id: str) -> list[VersionSummary]:
    with db_session() as connection:
        rows = connection.execute(
            """
            SELECT id, negotiation_id, version_number, uploaded_by, filename, created_at
            FROM version
            WHERE negotiation_id = ?
            ORDER BY version_number DESC
            """,
            (negotiation_id,),
        ).fetchall()

    return [
        VersionSummary(
            id=row["id"],
            negotiation_id=row["negotiation_id"],
            version_number=row["version_number"],
            uploaded_by=row["uploaded_by"],
            filename=row["filename"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
        for row in rows
    ]


def get_recent_annotation_examples(clause_type: str, limit: int) -> list[dict[str, str]]:
    with db_session() as connection:
        rows = connection.execute(
            """
            SELECT prompt, completion
            FROM training_example
            WHERE clause_type = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (clause_type, limit),
        ).fetchall()
    return [{"prompt": row["prompt"], "completion": row["completion"]} for row in rows]


def create_annotation(payload: AnnotationCreate) -> tuple[str, str | None]:
    annotation_id = str(uuid.uuid4())
    training_example_id = None
    with db_session() as connection:
        connection.execute(
            """
            INSERT INTO annotation (
                id, clause_id, redline_id, annotation_type, agent_risk_level, human_risk_level,
                correction_reasoning, was_corrected, confidence_rating, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                annotation_id,
                payload.clause_id,
                payload.redline_id,
                payload.annotation_type.value,
                payload.agent_risk_level.value if payload.agent_risk_level else None,
                payload.human_risk_level.value if payload.human_risk_level else None,
                payload.correction_reasoning,
                1 if payload.was_corrected else 0,
                payload.confidence_rating,
                _now(),
            ),
        )

        if payload.prompt and payload.completion:
            training_example_id = str(uuid.uuid4())
            connection.execute(
                """
                INSERT INTO training_example (
                    id, annotation_id, clause_type, prompt, completion, split, exported, created_at
                )
                VALUES (?, ?, ?, ?, ?, 'train', 0, ?)
                """,
                (
                    training_example_id,
                    annotation_id,
                    payload.clause_type.value if payload.clause_type else None,
                    payload.prompt,
                    payload.completion,
                    _now(),
                ),
            )

    return annotation_id, training_example_id
