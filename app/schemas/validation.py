from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.validation import ActionTaken, RuleResultStatus, ValidationRunStatus


class RuleResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    validation_run_id: str
    rule_id: str
    rule_name: str
    section: str
    status: RuleResultStatus
    confidence: float
    evidence: str | None
    ai_reasoning: str | None
    action_taken: ActionTaken
    reviewer_comment: str | None
    executed_at: datetime | None


class ValidationRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    deal_id: str
    checklist_id: str | None
    status: ValidationRunStatus
    total_rules: int
    passed: int
    warnings: int
    failed: int
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    rule_results: list[RuleResultResponse] = []


class ValidationTriggerResponse(BaseModel):
    validation_run_id: str
    deal_id: str
    message: str = "Validation started"


class ReviewerActionRequest(BaseModel):
    action: ActionTaken
    comment: str | None = None


class ReviewerActionResponse(BaseModel):
    result_id: str
    action_taken: ActionTaken
    message: str = "Action recorded"
