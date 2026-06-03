"""PAN card validation endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.pan_ocr_service import run_pan_ocr
from app.services.pan_validation_service import validate_pan_document

router = APIRouter(tags=["pan-validation"])

_ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "pdf"}
_MAX_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/validation/pan/validate-document")
async def validate_pan_document_endpoint(
    file: UploadFile = File(...),
    entity_type: str | None = Form(default=None),
    entity_id: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
):
    ext = (file.filename or "").lower().rsplit(".", 1)[-1] if "." in (file.filename or "") else ""
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '.{ext}'. Allowed: {', '.join(_ALLOWED_EXTENSIONS)}",
        )

    content = await file.read()
    if len(content) > _MAX_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 10 MB limit.")

    ocr_result = await run_pan_ocr(content, file.filename or "", file.content_type or "")

    result = await validate_pan_document(
        db=db,
        ocr=ocr_result,
        filename=file.filename,
    )

    return {
        "status": result.status,
        "extracted": result.extracted,
        "database": result.database,
        "rules": result.rules,
    }


@router.post("/validation/pan/validate-manual")
async def validate_pan_manual(
    pan_number: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Fallback: validate a PAN number entered manually (no OCR)."""
    from app.services.pan_ocr_service import OCRResult
    pan = pan_number.upper().replace(" ", "").replace("-", "").strip()
    ocr = OCRResult(pan_number=pan, confidence=None, raw_text=f"Manual input: {pan}")
    result = await validate_pan_document(db=db, ocr=ocr, filename=None)
    return {
        "status": result.status,
        "extracted": result.extracted,
        "database": result.database,
        "rules": result.rules,
    }
