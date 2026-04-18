import fitz  # PyMuPDF
import docx


# -----------------------------
# PDF TEXT EXTRACTION
# -----------------------------
def extract_pdf_text(file_path: str) -> str:
    doc = fitz.open(file_path)
    text = ""

    for page in doc:
        text += page.get_text()

    return text.strip()


# -----------------------------
# DOCX TEXT EXTRACTION
# -----------------------------
def extract_docx_text(file_path: str) -> str:
    doc = docx.Document(file_path)
    text = "\n".join([para.text for para in doc.paragraphs])

    return text.strip()


# -----------------------------
# MAIN UNIVERSAL PARSER
# -----------------------------
def extract_text(file_path: str, filename: str) -> str:
    filename = filename.lower()

    if filename.endswith(".pdf"):
        return extract_pdf_text(file_path)

    elif filename.endswith(".docx"):
        return extract_docx_text(file_path)

    elif filename.endswith(".txt"):
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    else:
        raise ValueError("Unsupported file format")