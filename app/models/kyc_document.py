import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EntityKycDocument(Base):
    __tablename__ = "entity_kyc_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    document_type: Mapped[str] = mapped_column(String(64), default="pan_card")
    original_file_name: Mapped[str | None] = mapped_column(String(512), nullable=True)

    extracted_pan_number: Mapped[str | None] = mapped_column(String(10), nullable=True)
    extracted_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    extracted_father_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    extracted_date_of_birth: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    ocr_raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    validation_status: Mapped[str] = mapped_column(String(16), default="PENDING")
    validation_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
