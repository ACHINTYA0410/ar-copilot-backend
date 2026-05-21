from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.deal import Deal, DealStatus
from app.models.validation import ValidationRun
from app.schemas.deal import (
    DealCreate, DealDetailResponse, DealListResponse, DealResponse,
    DealStatsResponse, DealUpdate, DocumentSummary, ValidationSummary,
)
from app.services.audit_service import AuditService

router = APIRouter(prefix="/deals", tags=["deals"])


def _to_deal_response(deal: Deal) -> DealResponse:
    return DealResponse.model_validate(deal)


@router.get("/stats", response_model=DealStatsResponse)
async def get_deal_stats(db: AsyncSession = Depends(get_db)):
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    needs_review = await db.scalar(
        select(func.count(Deal.id)).where(Deal.status == DealStatus.needs_review)
    )
    stuck = await db.scalar(
        select(func.count(Deal.id)).where(Deal.status == DealStatus.stuck)
    )
    auto_approved_today = await db.scalar(
        select(func.count(Deal.id)).where(
            Deal.status == DealStatus.auto_approved,
            Deal.updated_at >= today_start,
        )
    )
    auto_rejected_today = await db.scalar(
        select(func.count(Deal.id)).where(
            Deal.status == DealStatus.auto_rejected,
            Deal.updated_at >= today_start,
        )
    )

    return DealStatsResponse(
        needs_review=needs_review or 0,
        stuck=stuck or 0,
        auto_approved_today=auto_approved_today or 0,
        auto_rejected_today=auto_rejected_today or 0,
    )


@router.get("", response_model=DealListResponse)
async def list_deals(
    status: str | None = Query(None),
    submitted_by: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    q = select(Deal)

    if status:
        try:
            q = q.where(Deal.status == DealStatus(status))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    if submitted_by:
        q = q.where(Deal.submitted_by_name.ilike(f"%{submitted_by}%"))

    if search:
        q = q.where(
            Deal.customer_name.ilike(f"%{search}%") | Deal.id.ilike(f"%{search}%")
        )

    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    q = q.order_by(Deal.submitted_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    deals = result.scalars().all()

    return DealListResponse(
        items=[_to_deal_response(d) for d in deals],
        total=total or 0,
        page=page,
        page_size=page_size,
    )


@router.get("/{deal_id}", response_model=DealDetailResponse)
async def get_deal(deal_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Deal)
        .options(selectinload(Deal.documents), selectinload(Deal.validation_runs))
        .where(Deal.id == deal_id)
    )
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(status_code=404, detail=f"Deal {deal_id} not found")

    latest_run = None
    if deal.validation_runs:
        latest_run = sorted(deal.validation_runs, key=lambda r: r.created_at, reverse=True)[0]

    return DealDetailResponse(
        **_to_deal_response(deal).model_dump(),
        documents=[DocumentSummary.model_validate(doc) for doc in deal.documents],
        latest_validation=ValidationSummary.model_validate(latest_run) if latest_run else None,
    )


@router.post("", response_model=DealResponse, status_code=201)
async def create_deal(payload: DealCreate, db: AsyncSession = Depends(get_db)):
    import random
    deal_id = payload.id or f"DL-{random.randint(10000, 99999)}"

    existing = await db.get(Deal, deal_id)
    if existing:
        raise HTTPException(status_code=409, detail=f"Deal {deal_id} already exists")

    deal = Deal(
        id=deal_id,
        **payload.model_dump(exclude={"id"}),
    )
    db.add(deal)
    await db.flush()
    return _to_deal_response(deal)


@router.patch("/{deal_id}", response_model=DealResponse)
async def update_deal(deal_id: str, payload: DealUpdate, db: AsyncSession = Depends(get_db)):
    deal = await db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail=f"Deal {deal_id} not found")

    old_status = deal.status.value if deal.status else None
    update_data = payload.model_dump(exclude_none=True)

    for field, value in update_data.items():
        setattr(deal, field, value)

    if payload.status and old_status != payload.status.value:
        audit = AuditService(db)
        await audit.log_deal_status_change(
            actor_name="API User",
            deal_id=deal_id,
            old_status=old_status,
            new_status=payload.status.value,
        )

    await db.flush()
    await db.refresh(deal)
    return _to_deal_response(deal)
