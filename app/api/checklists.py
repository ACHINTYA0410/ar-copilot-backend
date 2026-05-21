from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.checklist import Checklist, ChecklistStatus
from app.schemas.checklist import (
    ChecklistCreate, ChecklistListResponse, ChecklistResponse, ChecklistUpdate,
)

router = APIRouter(prefix="/checklists", tags=["checklists"])


@router.get("", response_model=ChecklistListResponse)
async def list_checklists(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Checklist).order_by(Checklist.created_at.desc()))
    items = result.scalars().all()
    return ChecklistListResponse(
        items=[ChecklistResponse.model_validate(c) for c in items],
        total=len(items),
    )


@router.get("/{checklist_id}", response_model=ChecklistResponse)
async def get_checklist(checklist_id: str, db: AsyncSession = Depends(get_db)):
    checklist = await db.get(Checklist, checklist_id)
    if not checklist:
        raise HTTPException(status_code=404, detail="Checklist not found")
    return ChecklistResponse.model_validate(checklist)


@router.post("", response_model=ChecklistResponse, status_code=201)
async def create_checklist(payload: ChecklistCreate, db: AsyncSession = Depends(get_db)):
    checklist = Checklist(**payload.model_dump())
    db.add(checklist)
    await db.flush()
    return ChecklistResponse.model_validate(checklist)


@router.patch("/{checklist_id}", response_model=ChecklistResponse)
async def update_checklist(
    checklist_id: str, payload: ChecklistUpdate, db: AsyncSession = Depends(get_db)
):
    checklist = await db.get(Checklist, checklist_id)
    if not checklist:
        raise HTTPException(status_code=404, detail="Checklist not found")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(checklist, field, value)

    await db.flush()
    return ChecklistResponse.model_validate(checklist)


@router.post("/{checklist_id}/publish", response_model=ChecklistResponse)
async def publish_checklist(checklist_id: str, db: AsyncSession = Depends(get_db)):
    checklist = await db.get(Checklist, checklist_id)
    if not checklist:
        raise HTTPException(status_code=404, detail="Checklist not found")

    checklist.status = ChecklistStatus.active
    checklist.published_at = datetime.now(timezone.utc)
    await db.flush()
    return ChecklistResponse.model_validate(checklist)
