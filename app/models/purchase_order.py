import enum

from sqlalchemy import Column, DateTime, Enum, Integer, String
from sqlalchemy.sql import func

from app.database import Base


class POMode(str, enum.Enum):
    online = "online"
    offline = "offline"


class NotificationTarget(str, enum.Enum):
    school = "school"
    distributor = "distributor"


class OrderType(str, enum.Enum):
    forward = "forward"
    forward_counter_hardware = "forward_counter_hardware"
    forward_counter_books = "forward_counter_books"
    sampling = "sampling"


class OrderStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PO_APPROVAL_PENDING = "PO_APPROVAL_PENDING"
    FIN_HOLD = "FIN_HOLD"
    FIN_APPROVED = "FIN_APPROVED"
    DISCARDED = "DISCARDED"


class POLinkStatus(str, enum.Enum):
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    # --- Core identity — mirrors ORP column names exactly ---
    order_id = Column(String, primary_key=True)
    deal_id = Column(String, index=True, nullable=False)  # ORP's HubSpot deal ID, not local deals.id
    agreement_type = Column(String, nullable=False)
    order_academic_year = Column(String, nullable=False)
    order_type = Column(Enum(OrderType), nullable=False)
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)
    po_mode = Column(Enum(POMode), nullable=False)
    notification_sent_to = Column(Enum(NotificationTarget), nullable=False)

    # --- Workflow state --- mirrors ORP columns
    current_order_status = Column(Enum(OrderStatus), nullable=False, default=OrderStatus.DRAFT)
    finance_approval_by = Column(String, nullable=True)
    finance_approval_at = Column(DateTime, nullable=True)
    # Stored as integer minutes; compute human-readable duration in the provider layer
    approval_aging_minutes = Column(Integer, nullable=True)
    whatsapp_delivery_status = Column(String, nullable=True)  # "delivered" / "failed" / "pending"
    reminder_count = Column(Integer, nullable=False, default=0)
    po_rejected_at = Column(DateTime, nullable=True)
    po_rejection_reason = Column(String, nullable=True)

    # --- Customer-side approval --- mirrors ORP columns
    customer_name = Column(String, nullable=False)
    po_approved_by = Column(String, nullable=True)       # often external email (gmail/yahoo)
    po_approver_contact_no = Column(String, nullable=True)
    po_approved_on = Column(DateTime, nullable=True)
    po_verification_link = Column(String, nullable=True)
    po_link_status = Column(Enum(POLinkStatus), nullable=True)

    # --- Local metadata — NOT from ORP, added for our caching layer ---
    fetched_from_orp_at = Column(DateTime, server_default=func.now())
