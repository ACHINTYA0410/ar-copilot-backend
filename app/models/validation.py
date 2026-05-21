import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ValidationRunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class RuleResultStatus(str, enum.Enum):
    pass_ = "pass"
    warning = "warning"
    fail = "fail"
    pending = "pending"
    running = "running"


class ActionTaken(str, enum.Enum):
    none = "none"
    approve_anyway = "approve_anyway"
    reject_reason = "reject_reason"
    pending_review = "pending_review"


class ValidationRun(Base):
    __tablename__ = "validation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    deal_id: Mapped[str] = mapped_column(String(20), ForeignKey("deals.id"), nullable=False)
    checklist_id: Mapped[str] = mapped_column(String(36), ForeignKey("checklists.id"), nullable=True)

    status: Mapped[ValidationRunStatus] = mapped_column(
        Enum(ValidationRunStatus), default=ValidationRunStatus.pending
    )
    total_rules: Mapped[int] = mapped_column(Integer, default=0)
    passed: Mapped[int] = mapped_column(Integer, default=0)
    warnings: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    deal: Mapped["Deal"] = relationship("Deal", back_populates="validation_runs")  # noqa: F821
    rule_results: Mapped[list["RuleResult"]] = relationship(
        "RuleResult", back_populates="validation_run", cascade="all, delete-orphan"
    )


class RuleResult(Base):
    __tablename__ = "rule_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    validation_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("validation_runs.id"), nullable=False
    )
    rule_id: Mapped[str] = mapped_column(String(100), nullable=False)
    rule_name: Mapped[str] = mapped_column(String(255), nullable=False)
    section: Mapped[str] = mapped_column(String(100), nullable=False)

    status: Mapped[RuleResultStatus] = mapped_column(
        Enum(RuleResultStatus), default=RuleResultStatus.pending
    )
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    evidence: Mapped[str] = mapped_column(Text, nullable=True)
    ai_reasoning: Mapped[str] = mapped_column(Text, nullable=True)

    action_taken: Mapped[ActionTaken] = mapped_column(Enum(ActionTaken), default=ActionTaken.none)
    reviewer_comment: Mapped[str] = mapped_column(Text, nullable=True)

    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    validation_run: Mapped["ValidationRun"] = relationship(
        "ValidationRun", back_populates="rule_results"
    )
