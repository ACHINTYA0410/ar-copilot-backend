import os
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.config import settings
from app.models.document import DocumentType


class DocumentService:
    def __init__(self):
        self.upload_dir = Path(settings.UPLOAD_DIR)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.max_size_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    async def save(
        self,
        file: UploadFile,
        deal_id: str,
        document_type: DocumentType = DocumentType.other,
    ) -> dict:
        content = await file.read()

        if len(content) > self.max_size_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds maximum size of {settings.MAX_UPLOAD_SIZE_MB}MB",
            )

        doc_id = str(uuid.uuid4())
        ext = Path(file.filename or "file").suffix or ".bin"
        stored_filename = f"{doc_id}{ext}"
        deal_dir = self.upload_dir / deal_id
        deal_dir.mkdir(parents=True, exist_ok=True)
        file_path = deal_dir / stored_filename

        with open(file_path, "wb") as f:
            f.write(content)

        return {
            "id": doc_id,
            "filename": stored_filename,
            "original_filename": file.filename or stored_filename,
            "file_path": str(file_path),
            "file_size": len(content),
            "page_count": 0,  # PDF parsing deferred to Step C
        }

    def get_path(self, file_path: str) -> Path:
        path = Path(file_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Document file not found")
        return path

    def delete(self, file_path: str) -> None:
        path = Path(file_path)
        if path.exists():
            os.remove(path)
