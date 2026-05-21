from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.audit import ActionType, ActorType, TargetType


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    timestamp: datetime
    actor_type: ActorType
    actor_name: str
    action_type: ActionType
    target_type: TargetType
    target_id: str
    description: str
    before_value: dict[str, Any] | None
    after_value: dict[str, Any] | None
    metadata_: dict[str, Any] | None = None


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int


class WeeklyStatPoint(BaseModel):
    date: str
    approved: int
    rejected: int
    auto_processed: int


class AuditStatsResponse(BaseModel):
    compliance_score: float
    total_actions_7d: int
    approvals_7d: int
    rejections_7d: int
    auto_processed_7d: int
    rule_changes_7d: int
    weekly_trend: list[WeeklyStatPoint]
