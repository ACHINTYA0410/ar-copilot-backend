import enum
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ActionOnFail(str, enum.Enum):
    auto_reject = "auto_reject"
    flag_review = "flag_review"
    warning = "warning"


class Rule(Base):
    __tablename__ = "rules"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    section: Mapped[str] = mapped_column(String(100), nullable=False)

    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    required_context: Mapped[list] = mapped_column(JSON, default=list)
    confidence_threshold: Mapped[float] = mapped_column(Float, default=0.75)
    action_on_fail: Mapped[ActionOnFail] = mapped_column(
        Enum(ActionOnFail), default=ActionOnFail.flag_review
    )
    error_message: Mapped[str] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    fired_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_runtime_ms: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
