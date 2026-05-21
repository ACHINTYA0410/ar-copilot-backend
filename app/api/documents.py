from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.document import Document, DocumentStatus, DocumentType
from app.schemas.document import DocumentResponse, DocumentUploadResponse
from app.services.audit_service import AuditService
from app.services.document_service import DocumentService

router = APIRouter(tags=["documents"])
doc_service = DocumentService()


@router.post("/deals/{deal_id}/documents", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(
    deal_id: str,
    file: UploadFile,
    document_type: str = Form(default="other"),
    db: AsyncSession = Depends(get_db),
):
    try:
        doc_type = DocumentType(document_type)
    except ValueError:
        doc_type = DocumentType.other

    saved = await doc_service.save(file, deal_id, doc_type)

    doc = Document(
        id=saved["id"],
        deal_id=deal_id,
        filename=saved["filename"],
        original_filename=saved["original_filename"],
        file_path=saved["file_path"],
        file_size=saved["file_size"],
        page_count=saved["page_count"],
        document_type=doc_type,
        status=DocumentStatus.pending,
    )
    db.add(doc)

    audit = AuditService(db)
    await audit.log_upload("API User", deal_id, saved["original_filename"])
    await db.flush()

    return DocumentUploadResponse(
        id=doc.id,
        deal_id=deal_id,
        original_filename=doc.original_filename,
        document_type=doc_type,
        file_size=doc.file_size,
    )


@router.get("/documents/{doc_id}", response_class=FileResponse)
async def download_document(doc_id: str, db: AsyncSession = Depends(get_db)):
    doc = await db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    path = doc_service.get_path(doc.file_path)
    return FileResponse(path=str(path), filename=doc.original_filename)


@router.get("/documents/{doc_id}/info", response_model=DocumentResponse)
async def get_document_info(doc_id: str, db: AsyncSession = Depends(get_db)):
    doc = await db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse.model_validate(doc)


@router.delete("/documents/{doc_id}", status_code=204)
async def delete_document(doc_id: str, db: AsyncSession = Depends(get_db)):
    doc = await db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    doc_service.delete(doc.file_path)
    await db.delete(doc)
    await db.flush()
