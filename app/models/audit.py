import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ActorType(str, enum.Enum):
    user = "user"
    ai_agent = "ai_agent"
    system = "system"


class ActionType(str, enum.Enum):
    approved = "approved"
    rejected = "rejected"
    modified_rule = "modified_rule"
    uploaded = "uploaded"
    auto_approved = "auto_approved"
    auto_rejected = "auto_rejected"
    pattern_detected = "pattern_detected"
    override = "override"


class TargetType(str, enum.Enum):
    deal = "deal"
    rule = "rule"
    checklist = "checklist"
    document = "document"


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    actor_type: Mapped[ActorType] = mapped_column(Enum(ActorType), nullable=False)
    actor_name: Mapped[str] = mapped_column(String(100), nullable=False)

    action_type: Mapped[ActionType] = mapped_column(Enum(ActionType), nullable=False)
    target_type: Mapped[TargetType] = mapped_column(Enum(TargetType), nullable=False)
    target_id: Mapped[str] = mapped_column(String(100), nullable=False)

    description: Mapped[str] = mapped_column(Text, nullable=False)
    before_value: Mapped[dict] = mapped_column(JSON, nullable=True)
    after_value: Mapped[dict] = mapped_column(JSON, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, nullable=True)
