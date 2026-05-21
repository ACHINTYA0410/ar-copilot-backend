import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DocumentType(str, enum.Enum):
    agreement = "agreement"
    pan_card = "pan_card"
    gst_certificate = "gst_certificate"
    po = "po"
    other = "other"


class DocumentStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    validated = "validated"
    issues_found = "issues_found"
    failed = "failed"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    deal_id: Mapped[str] = mapped_column(String(20), ForeignKey("deals.id"), nullable=False)

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    page_count: Mapped[int] = mapped_column(Integer, default=0)

    document_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType), default=DocumentType.other
    )
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus), default=DocumentStatus.pending
    )

    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    deal: Mapped["Deal"] = relationship("Deal", back_populates="documents")  # noqa: F821
