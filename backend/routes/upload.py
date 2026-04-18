from fastapi import APIRouter, UploadFile, File, HTTPException
import os

from backend.services.file_parser import extract_text
from backend.routes.analyze import analyze_cta, CTARequest

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# =========================
# UPLOAD + AUTO ANALYZE PIPELINE
# =========================
@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):

    file_path = os.path.join(UPLOAD_DIR, file.filename)

    # -------------------------
    # 1. SAVE FILE
    # -------------------------
    content = await file.read()

    with open(file_path, "wb") as f:
        f.write(content)

    # -------------------------
    # 2. EXTRACT TEXT (REAL LOGIC)
    # -------------------------
    try:
        text = extract_text(file_path, file.filename)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"File parsing failed: {str(e)}"
        )

    # -------------------------
    # 3. CALL ANALYSIS ENGINE
    # -------------------------
    result = analyze_cta(
        CTARequest(
            filename=file.filename,
            text=text,
            gemini_key=None
        )
    )

    # -------------------------
    # 4. RETURN FINAL RESPONSE
    # -------------------------
    return {
        "status": "success",
        "filename": file.filename,
        "text_preview": text[:500],
        "analysis": result
    }