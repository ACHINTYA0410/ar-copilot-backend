import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ChecklistStatus(str, enum.Enum):
    active = "active"
    draft = "draft"
    deprecated = "deprecated"


class Checklist(Base):
    __tablename__ = "checklists"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[ChecklistStatus] = mapped_column(
        Enum(ChecklistStatus), default=ChecklistStatus.draft
    )

    rule_ids: Mapped[list] = mapped_column(JSON, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
