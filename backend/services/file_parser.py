from pathlib import Path


def _read_pdf(file_path: str) -> str:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required to parse PDF files.") from exc

    with fitz.open(file_path) as document:
        return "\n".join(page.get_text() for page in document).strip()


def _read_docx(file_path: str) -> str:
    try:
        import docx
    except ImportError as exc:
        raise RuntimeError("python-docx is required to parse DOCX files.") from exc

    document = docx.Document(file_path)
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
