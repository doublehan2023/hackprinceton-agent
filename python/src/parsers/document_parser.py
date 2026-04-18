from __future__ import annotations

from pathlib import Path

from docx import Document
from PyPDF2 import PdfReader


def _read_pdf(file_path: str) -> str:
    reader = PdfReader(file_path)
    return "\n".join((page.extract_text() or "").strip() for page in reader.pages).strip()


def _read_docx(file_path: str) -> str:
    document = Document(file_path)
    return "\n".join(paragraph.text for paragraph in document.paragraphs).strip()


def extract_text(file_path: str, filename: str | None = None) -> str:
    suffix = (filename or Path(file_path).name).lower()
    if suffix.endswith(".pdf"):
        return _read_pdf(file_path)
    if suffix.endswith(".docx"):
        return _read_docx(file_path)
    if suffix.endswith(".txt"):
        return Path(file_path).read_text(encoding="utf-8")
    raise ValueError("Unsupported file format. Expected PDF, DOCX, or TXT.")
