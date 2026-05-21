from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.document import DocumentStatus, DocumentType


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    deal_id: str
    filename: str
    original_filename: str
    file_size: int
    page_count: int
    document_type: DocumentType
    status: DocumentStatus
    uploaded_at: datetime


class DocumentUploadResponse(BaseModel):
    id: str
    deal_id: str
    original_filename: str
    document_type: DocumentType
    file_size: int
    message: str = "Document uploaded successfully"
