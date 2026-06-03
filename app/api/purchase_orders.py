from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, get_db
from app.schemas.validation import ValidationTriggerResponse
from app.services.orp_provider import ORPContextProvider, get_orp_provider

router = APIRouter(prefix="/purchase-orders", tags=["purchase-orders"])


def _make_provider(db: AsyncSession = Depends(get_db)) -> ORPContextProvider:
    return get_orp_provider(db)


@router.get("")
async def list_purchase_orders(
    deal_id: Optional[str] = None,
    academic_year: Optional[str] = None,
    order_type: Optional[str] = None,
    po_mode: Optional[str] = None,
    created_by: Optional[str] = None,
    provider: ORPContextProvider = Depends(_make_provider),
):
    filters = {}
    if deal_id:
        filters["deal_id"] = deal_id
    if academic_year:
        filters["academic_year"] = academic_year
    if order_type:
        filters["order_type"] = order_type
    if po_mode:
        filters["po_mode"] = po_mode
    if created_by:
        filters["created_by"] = created_by
    return await provider.list_pos(filters)


@router.get("/{order_id}")
async def get_purchase_order(
    order_id: str,
    provider: ORPContextProvider = Depends(_make_provider),
):
    po = await provider.get_po(order_id)
    if not po:
        raise HTTPException(status_code=404, detail=f"PO {order_id!r} not found")
    return po


@router.post("/{order_id}/validate", response_model=ValidationTriggerResponse, status_code=202)
async def validate_purchase_order(
    order_id: str,
    background_tasks: BackgroundTasks,
    checklist_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    from app.models.validation import ValidationRun, ValidationRunStatus
    from app.services.validation_engine import ValidationEngine

    provider = get_orp_provider(db)
    po = await provider.get_po(order_id)
    if not po:
        raise HTTPException(status_code=404, detail=f"PO {order_id!r} not found")

    if not checklist_id:
        # Default to the PO validation checklist if available, else the first active checklist
        from sqlalchemy import select
        from app.models.checklist import Checklist
        result = await db.execute(
            select(Checklist)
            .where(Checklist.id == "checklist_po_validation_v1")
            .limit(1)
        )
        cl = result.scalar_one_or_none()
        checklist_id = cl.id if cl else "checklist_po_validation_v1"

    run = ValidationRun(
        deal_id=None,
        target_type="po",
        target_id=order_id,
        checklist_id=checklist_id,
        status=ValidationRunStatus.pending,
    )
    db.add(run)
    await db.flush()
    run_id = run.id
    await db.commit()

    async def _run():
        async with AsyncSessionLocal() as session:
            eng = ValidationEngine(session)
            # Exhaust the generator; each yield commits a RuleResult to the DB
            async for _result in eng.run_po_checklist(order_id, checklist_id):
                _ = _result

    background_tasks.add_task(_run)

    return ValidationTriggerResponse(validation_run_id=run_id, order_id=order_id)
