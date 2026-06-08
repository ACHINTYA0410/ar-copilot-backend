"""
Sample PO dicts for testing the Groq PO confidence scoring layer.

Three scenarios:
  PO_CLEAN         — all fields healthy, should produce high confidence across all rules
  PO_INACTIVE_LINK — customer verification link is INACTIVE (warning scenario)
  PO_NULL_FINANCE  — PO is in FIN_HOLD with no approval_aging_minutes recorded (warning scenario)
"""

# Scenario 1: Clean PO — everything looks good
PO_CLEAN = {
    "order_id": "TEST-001",
    "deal_id": "DL-99001",
    "_linked_deal_found": True,
    "order_academic_year": "26-27",
    "created_by": "rahul.sharma@leadschool.in",
    "current_order_status": "FIN_APPROVED",
    "po_link_status": "APPROVED",
    "po_approved_on": "2026-04-15T10:30:00",
    "approval_aging_minutes": None,
    "customer_name": "Sunrise Public School",
    "notification_sent_to": "school",
    "amount": 85000,
    "po_type": "forward",
}

# Scenario 2: PO with an inactive verification link (warning)
PO_INACTIVE_LINK = {
    "order_id": "TEST-002",
    "deal_id": "DL-99002",
    "_linked_deal_found": True,
    "order_academic_year": "26-27",
    "created_by": "priya.nair@leadschool.in",
    "current_order_status": "ACTIVE",
    "po_link_status": "INACTIVE",
    "po_approved_on": None,
    "approval_aging_minutes": None,
    "customer_name": "Bright Future Academy",
    "notification_sent_to": "school",
    "amount": 42000,
    "po_type": "forward",
}

# Scenario 3: PO stuck in FIN_HOLD with no aging timestamp (warning)
PO_NULL_FINANCE = {
    "order_id": "TEST-003",
    "deal_id": "DL-99003",
    "_linked_deal_found": True,
    "order_academic_year": "26-27",
    "created_by": "amit.verma@leadschool.in",
    "current_order_status": "FIN_HOLD",
    "po_link_status": None,
    "po_approved_on": None,
    "approval_aging_minutes": None,
    "customer_name": "Green Valley School",
    "notification_sent_to": "distributor",
    "amount": 67500,
    "po_type": "forward_counter",
}
