from abc import ABC, abstractmethod
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.purchase_order import PurchaseOrder


class ORPContextProvider(ABC):
    """Abstract interface for fetching PO data from ORP.

    Swap implementations (LocalSQLiteORPProvider → MySQLORPProvider / APIORPProvider)
    without touching rules or the validation engine. All implementations must return
    the same dict shape from _to_dict so downstream consumers stay stable.
    """

    @abstractmethod
    async def get_po(self, order_id: str) -> Optional[dict]:
        """Fetch one PO by Order ID. Returns dict or None if not found."""
        ...

    @abstractmethod
    async def list_pos(self, filters: dict) -> list[dict]:
        """Fetch POs matching filters (deal_id, academic_year, order_type, po_mode)."""
        ...


class LocalSQLiteORPProvider(ORPContextProvider):
    """v1: reads from local purchase_orders table seeded with ORP sample data.

    Replace with MySQLORPProvider or APIORPProvider when real ORP access arrives.
    Change ORP_PROVIDER in config (or .env) — nothing else needs to change.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_po(self, order_id: str) -> Optional[dict]:
        result = await self.session.execute(
            select(PurchaseOrder).where(PurchaseOrder.order_id == order_id)
        )
        po = result.scalar_one_or_none()
        return self._to_dict(po) if po else None

    async def list_pos(self, filters: dict) -> list[dict]:
        query = select(PurchaseOrder)
        if filters.get("deal_id"):
            query = query.where(PurchaseOrder.deal_id == filters["deal_id"])
        if filters.get("academic_year"):
            query = query.where(PurchaseOrder.order_academic_year == filters["academic_year"])
        if filters.get("order_type"):
            query = query.where(PurchaseOrder.order_type == filters["order_type"])
        if filters.get("po_mode"):
            query = query.where(PurchaseOrder.po_mode == filters["po_mode"])
        if filters.get("created_by"):
            query = query.where(PurchaseOrder.created_by == filters["created_by"])
        result = await self.session.execute(query)
        return [self._to_dict(po) for po in result.scalars().all()]

    @staticmethod
    def _to_dict(po: PurchaseOrder) -> dict:
        """Stable contract — all provider implementations must return this shape."""
        return {
            # Core identity
            "order_id": po.order_id,
            "deal_id": po.deal_id,
            "customer_name": po.customer_name,
            "agreement_type": po.agreement_type,
            "order_academic_year": po.order_academic_year,
            "order_type": po.order_type.value,
            "created_by": po.created_by,
            "created_at": po.created_at.isoformat(),
            "po_mode": po.po_mode.value,
            "notification_sent_to": po.notification_sent_to.value,
            # Workflow state
            "current_order_status": po.current_order_status.value,
            "finance_approval_by": po.finance_approval_by,
            "finance_approval_at": po.finance_approval_at.isoformat() if po.finance_approval_at else None,
            "approval_aging_minutes": po.approval_aging_minutes,
            "whatsapp_delivery_status": po.whatsapp_delivery_status,
            "reminder_count": po.reminder_count,
            "po_rejected_at": po.po_rejected_at.isoformat() if po.po_rejected_at else None,
            "po_rejection_reason": po.po_rejection_reason,
            # Customer-side approval
            "po_approved_by": po.po_approved_by,
            "po_approver_contact_no": po.po_approver_contact_no,
            "po_approved_on": po.po_approved_on.isoformat() if po.po_approved_on else None,
            "po_verification_link": po.po_verification_link,
            "po_link_status": po.po_link_status.value if po.po_link_status else None,
            # Local metadata
            "fetched_from_orp_at": po.fetched_from_orp_at.isoformat() if po.fetched_from_orp_at else None,
        }


def get_orp_provider(session: AsyncSession) -> ORPContextProvider:
    """Factory used as a FastAPI dependency. Change ORP_PROVIDER in .env to swap implementations."""
    from app.config import settings

    if settings.ORP_PROVIDER == "local_sqlite":
        return LocalSQLiteORPProvider(session)
    # Future implementations registered here:
    # elif settings.ORP_PROVIDER == "mysql":
    #     return MySQLORPProvider(...)
    # elif settings.ORP_PROVIDER == "api":
    #     return APIORPProvider(...)
    raise ValueError(f"Unknown ORP_PROVIDER: {settings.ORP_PROVIDER!r}")
