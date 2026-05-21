from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.checklist import ChecklistStatus


class ChecklistBase(BaseModel):
    name: str
    version: str
    rule_ids: list[str] = []


class ChecklistCreate(ChecklistBase):
    pass


class ChecklistUpdate(BaseModel):
    name: str | None = None
    version: str | None = None
    rule_ids: list[str] | None = None


class ChecklistResponse(ChecklistBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    status: ChecklistStatus
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None


class ChecklistListResponse(BaseModel):
    items: list[ChecklistResponse]
    total: int
