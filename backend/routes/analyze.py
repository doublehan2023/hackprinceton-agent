from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend.core.config import get_settings
from backend.schemas import AnalyzeRequest, AnalyzeResponse
from backend.services.file_parser import extract_text
from backend.services.orchestrator import AnalysisOrchestrator

router = APIRouter()
orchestrator = AnalysisOrchestrator()


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_contract(
    negotiation_id: str | None = Form(default=None),
    title: str = Form(...),
    sponsor: str | None = Form(default=None),
    site: str | None = Form(default=None),
    pen_holder: str | None = Form(default=None),
    uploaded_by: str | None = Form(default=None),
    text: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
):
    if not text and not file:
        raise HTTPException(status_code=400, detail="Provide raw text or an uploaded CTA file.")

    filename = "inline.txt"
    raw_text = text or ""

    if file is not None:
        settings = get_settings()
        settings.upload_dir.mkdir(parents=True, exist_ok=True)
        filename = file.filename or "uploaded.txt"
        file_path = settings.upload_dir / Path(filename).name
        file_path.write_bytes(await file.read())
        try:
            raw_text = extract_text(str(file_path), filename)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"File parsing failed: {exc}") from exc

    payload = AnalyzeRequest(
        negotiation_id=negotiation_id,
        title=title,
        sponsor=sponsor,
        site=site,
        pen_holder=pen_holder,
        uploaded_by=uploaded_by,
        filename=filename,
        text=raw_text,
    )
    return await orchestrator.run(payload)
