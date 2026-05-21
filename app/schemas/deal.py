from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.deal import DealStatus


class DealBase(BaseModel):
    customer_name: str
    amount: Decimal
    status: DealStatus = DealStatus.needs_review
    submitted_by_name: str
    submitted_by_zone: str
    submitted_by_avatar_color: str = "#6366f1"
    submitted_at: datetime
    region: str | None = None
    products: list[str] = Field(default_factory=list)
    first_pass_rate: int = 0


class DealCreate(DealBase):
    id: str | None = None


class DealUpdate(BaseModel):
    status: DealStatus | None = None
    customer_name: str | None = None
    amount: Decimal | None = None


class DocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    original_filename: str
    document_type: str
    status: str
    file_size: int
    uploaded_at: datetime


class ValidationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    status: str
    total_rules: int
    passed: int
    warnings: int
    failed: int
    started_at: datetime | None
    completed_at: datetime | None


class DealResponse(DealBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    validation_score_passed: int
    validation_score_total: int
    critical_issues_count: int
    created_at: datetime
    updated_at: datetime


class DealDetailResponse(DealResponse):
    documents: list[DocumentSummary] = Field(default_factory=list)
    latest_validation: ValidationSummary | None = None


class DealListResponse(BaseModel):
    items: list[DealResponse]
    total: int
    page: int
    page_size: int


class DealStatsResponse(BaseModel):
    needs_review: int
    stuck: int
    auto_approved_today: int
    auto_rejected_today: int
