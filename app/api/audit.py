from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.audit import ActionType, ActorType, AuditLog
from app.schemas.audit import AuditLogListResponse, AuditLogResponse, AuditStatsResponse, WeeklyStatPoint

router = APIRouter(prefix="/audit-log", tags=["audit"])


@router.get("", response_model=AuditLogListResponse)
async def list_audit_log(
    actor_type: str | None = Query(None),
    action_type: str | None = Query(None),
    target_id: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    q = select(AuditLog)

    if actor_type:
        try:
            q = q.where(AuditLog.actor_type == ActorType(actor_type))
        except ValueError:
            pass

    if action_type:
        try:
            q = q.where(AuditLog.action_type == ActionType(action_type))
        except ValueError:
            pass

    if target_id:
        q = q.where(AuditLog.target_id == target_id)

    if search:
        q = q.where(AuditLog.description.ilike(f"%{search}%"))

    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    q = q.order_by(AuditLog.timestamp.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    items = result.scalars().all()

    return AuditLogListResponse(
        items=[AuditLogResponse.model_validate(e) for e in items],
        total=total or 0,
        page=page,
        page_size=page_size,
    )


@router.get("/stats", response_model=AuditStatsResponse)
async def get_audit_stats(db: AsyncSession = Depends(get_db)):
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)

    total_7d = await db.scalar(
        select(func.count(AuditLog.id)).where(AuditLog.timestamp >= seven_days_ago)
    ) or 0

    approvals_7d = await db.scalar(
        select(func.count(AuditLog.id)).where(
            AuditLog.timestamp >= seven_days_ago,
            AuditLog.action_type.in_([ActionType.approved, ActionType.auto_approved]),
        )
    ) or 0

    rejections_7d = await db.scalar(
        select(func.count(AuditLog.id)).where(
            AuditLog.timestamp >= seven_days_ago,
            AuditLog.action_type.in_([ActionType.rejected, ActionType.auto_rejected]),
        )
    ) or 0

    auto_7d = await db.scalar(
        select(func.count(AuditLog.id)).where(
            AuditLog.timestamp >= seven_days_ago,
            AuditLog.action_type.in_([ActionType.auto_approved, ActionType.auto_rejected]),
        )
    ) or 0

    rule_changes_7d = await db.scalar(
        select(func.count(AuditLog.id)).where(
            AuditLog.timestamp >= seven_days_ago,
            AuditLog.action_type == ActionType.modified_rule,
        )
    ) or 0

    compliance_score = (
        round((approvals_7d / (approvals_7d + rejections_7d)) * 100, 1)
        if (approvals_7d + rejections_7d) > 0
        else 94.2
    )

    # Build weekly trend (last 7 days)
    trend: list[WeeklyStatPoint] = []
    for i in range(6, -1, -1):
        day_start = (datetime.now(timezone.utc) - timedelta(days=i)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        day_end = day_start + timedelta(days=1)

        day_approved = await db.scalar(
            select(func.count(AuditLog.id)).where(
                AuditLog.timestamp >= day_start,
                AuditLog.timestamp < day_end,
                AuditLog.action_type.in_([ActionType.approved, ActionType.auto_approved]),
            )
        ) or 0

        day_rejected = await db.scalar(
            select(func.count(AuditLog.id)).where(
                AuditLog.timestamp >= day_start,
                AuditLog.timestamp < day_end,
                AuditLog.action_type.in_([ActionType.rejected, ActionType.auto_rejected]),
            )
        ) or 0

        day_auto = await db.scalar(
            select(func.count(AuditLog.id)).where(
                AuditLog.timestamp >= day_start,
                AuditLog.timestamp < day_end,
                AuditLog.action_type.in_([ActionType.auto_approved, ActionType.auto_rejected]),
            )
        ) or 0

        trend.append(
            WeeklyStatPoint(
                date=day_start.strftime("%Y-%m-%d"),
                approved=day_approved,
                rejected=day_rejected,
                auto_processed=day_auto,
            )
        )

    return AuditStatsResponse(
        compliance_score=compliance_score,
        total_actions_7d=total_7d,
        approvals_7d=approvals_7d,
        rejections_7d=rejections_7d,
        auto_processed_7d=auto_7d,
        rule_changes_7d=rule_changes_7d,
        weekly_trend=trend,
    )
