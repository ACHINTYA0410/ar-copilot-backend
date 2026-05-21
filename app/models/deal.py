import enum
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DealStatus(str, enum.Enum):
    needs_review = "needs_review"
    auto_approved = "auto_approved"
    auto_rejected = "auto_rejected"
    approved = "approved"
    rejected = "rejected"
    stuck = "stuck"


class Deal(Base):
    __tablename__ = "deals"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    status: Mapped[DealStatus] = mapped_column(Enum(DealStatus), default=DealStatus.needs_review)

    submitted_by_name: Mapped[str] = mapped_column(String(100), nullable=False)
    submitted_by_zone: Mapped[str] = mapped_column(String(100), nullable=False)
    submitted_by_avatar_color: Mapped[str] = mapped_column(String(20), default="#6366f1")
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    validation_score_passed: Mapped[int] = mapped_column(Integer, default=0)
    validation_score_total: Mapped[int] = mapped_column(Integer, default=0)
    critical_issues_count: Mapped[int] = mapped_column(Integer, default=0)

    region: Mapped[str] = mapped_column(String(100), nullable=True)
    products: Mapped[list] = mapped_column(JSON, default=list)
    first_pass_rate: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    documents: Mapped[list["Document"]] = relationship(  # noqa: F821
        "Document", back_populates="deal", cascade="all, delete-orphan"
    )
    validation_runs: Mapped[list["ValidationRun"]] = relationship(  # noqa: F821
        "ValidationRun", back_populates="deal", cascade="all, delete-orphan"
    )
