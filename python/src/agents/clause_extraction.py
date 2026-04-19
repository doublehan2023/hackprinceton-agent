from __future__ import annotations

import logging

from src.config import get_settings
from src.llm import build_messages, get_llm_client, parse_json_response
from src.nlp.legal_nlp import extract_clauses
from src.pipeline.state import Clause, ClauseType, ContractReviewState, Section
from src.utils.coercion import coerce_clause_type, coerce_confidence

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a legal contract clause extraction expert.

Extract contract clauses from the provided text and return valid JSON only.

Use this schema exactly:
{
  "clauses": [
    {
      "text": "full clause text",
      "clause_type": "one of the allowed clause types",
      "section_title": "section heading if available, otherwise null",
      "section_order": 1,
      "evidence": ["keyword or phrase that supports the classification"],
      "classification_confidence": 0.0
    }
  ]
}

Allowed clause_type values:
- Confidentiality
- Indemnification
- Payment Terms
- Intellectual Property
- Publication Rights
- Termination
- Governing Law
- Subject Injury
- Protocol Deviations
- General Clause

Rules:
- Return JSON only, with no markdown fences.
- Preserve clause ordering from the source text.
- classification_confidence must be between 0 and 1.
- Keep clause text faithful to the source.
- If a section heading is unknown, use null for section_title and null for section_order.
"""


class ClauseExtractionAgent:
    def __init__(self) -> None:
        self.llm = None
        self.extraction_model = "llm"

    def _ensure_llm(self) -> None:
        if self.llm is None:
            self.llm, runtime = get_llm_client()
            self.extraction_model = runtime.provider_name if runtime.enabled else "rules"

    def __call__(self, state: ContractReviewState) -> dict[str, object]:
        source_text = state.raw_text.strip()
        if not source_text:
            return {"clauses": [], "extraction_model": state.extraction_model}

        self._ensure_llm()
        if self.llm is None:
            logger.info(
                "No %s configured for clause extraction; using rules fallback.",
                self.extraction_model,
            )
            return self._fallback_result(state)

        try:
            payload = self._extract_with_llm(source_text, state.sections)
            clauses = self._parse_clauses(payload, state.sections)
            if clauses:
                return {
                    "clauses": clauses,
                    "extraction_model": self.extraction_model,
                }
            logger.warning(
                "%s clause extraction returned no clauses; using rules fallback.",
                self.extraction_model.upper(),
            )
        except Exception as exc:  # pragma: no cover - exercised by integration behavior
            logger.warning(
                "%s clause extraction failed; using rules fallback: %s",
                self.extraction_model.upper(),
                exc,
            )

        return self._fallback_result(state)

    def _prepare_text(self, raw_text: str, sections: list[Section]) -> str:
        if sections:
            formatted_sections: list[str] = []
            for section in sections:
                header = f"[Section {section.source_order}]"
                if section.title:
                    header = f"{header} {section.title}"
                formatted_sections.append(f"{header}\n{section.body.strip()}")
            text = "\n\n".join(formatted_sections).strip()
        else:
            text = raw_text

        max_chars = 15000
        if len(text) > max_chars:
            return text[:max_chars] + "\n\n[TRUNCATED]"
        return text

    def _extract_with_llm(self, raw_text: str, sections: list[Section]) -> dict[str, object]:
        prompt_text = self._prepare_text(raw_text, sections)
        messages = build_messages(
            SYSTEM_PROMPT,
            f"Extract structured clauses from this contract:\n\n{prompt_text}",
        )
        response = self.llm.invoke(messages)
        return parse_json_response(response)

    def _parse_clauses(self, payload: dict[str, object], sections: list[Section]) -> list[Clause]:
        section_lookup = {section.source_order: section for section in sections}
        clauses: list[Clause] = []

        for index, item in enumerate(payload.get("clauses", []), start=1):
            if not isinstance(item, dict):
                continue

            clause_text = str(item.get("text", "")).strip()
            if not clause_text:
                continue

            raw_type = str(item.get("clause_type", ClauseType.GENERAL.value))
            clause_type = coerce_clause_type(raw_type)
            section_order = self._coerce_int(item.get("section_order"))
            section_title = item.get("section_title")
            if section_title is not None:
                section_title = str(section_title)
            elif section_order in section_lookup:
                section_title = section_lookup[section_order].title

            evidence = item.get("evidence", [])
            if not isinstance(evidence, list):
                evidence = []

            confidence = coerce_confidence(item.get("classification_confidence"))

            clauses.append(
                Clause(
                    id=f"clause-{index}",
                    clause_type=clause_type,
                    text=clause_text,
                    source_order=index,
                    section_title=section_title,
                    section_order=section_order,
                    evidence=[str(value) for value in evidence if str(value).strip()],
                    classification_confidence=confidence,
                )
            )

        max_clauses = get_settings().analysis_max_clauses
        return clauses[:max_clauses]

    def _coerce_int(self, value: object) -> int | None:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def _fallback_result(self, state: ContractReviewState) -> dict[str, object]:
        return {
            "clauses": extract_clauses(
                state.raw_text,
                max_clauses=get_settings().analysis_max_clauses,
                sections=state.sections,
            ),
            "extraction_model": "rules",
        }
