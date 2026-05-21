from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.rule import ActionOnFail


class RuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    section: str
    prompt: str
    required_context: list[str]
    confidence_threshold: float
    action_on_fail: ActionOnFail
    error_message: str | None
    is_active: bool
    fired_count: int
    avg_runtime_ms: int
    created_at: datetime
    updated_at: datetime


class RuleUpdate(BaseModel):
    name: str | None = None
    prompt: str | None = None
    confidence_threshold: float | None = None
    action_on_fail: ActionOnFail | None = None
    error_message: str | None = None
    is_active: bool | None = None


class RulesBySectionResponse(BaseModel):
    section: str
    rules: list[RuleResponse]


class RuleTestRequest(BaseModel):
    deal_id: str
    document_ids: list[str] = []


class RuleTestResponse(BaseModel):
    rule_id: str
    status: str
    confidence: float
    evidence: str
    reasoning: str
    runtime_ms: int
