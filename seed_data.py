"""
Seed data script — populates the DB with realistic mock data.
Run with: python seed_data.py
"""
import asyncio
import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, create_tables
from app.models.audit import ActionType, ActorType, AuditLog, TargetType
from app.models.checklist import Checklist, ChecklistStatus
from app.models.deal import Deal, DealStatus
from app.models.document import Document, DocumentStatus, DocumentType
from app.models.purchase_order import NotificationTarget, OrderStatus, OrderType, POLinkStatus, POMode, PurchaseOrder
from app.models.rule import ActionOnFail, Rule
from app.models.validation import ActionTaken, RuleResult, RuleResultStatus, ValidationRun, ValidationRunStatus

NOW = datetime.now(timezone.utc)


def days_ago(n: float) -> datetime:
    return NOW - timedelta(days=n)


def rand_color() -> str:
    colors = ["#6366f1", "#8b5cf6", "#ec4899", "#f59e0b", "#10b981", "#3b82f6", "#ef4444", "#14b8a6"]
    return random.choice(colors)


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------
RULES_DATA = [
    # Document Content
    ("rule_check_signatures", "Signatures & Seal Verification", "Document Content",
     "Verify all required signatures and corporate seals on agreement.", ["documents"], 0.80, ActionOnFail.auto_reject,
     "One or more required signatures are missing or illegible."),
    ("rule_check_pan_attached", "PAN Card Attached & Valid", "Document Content",
     "Verify PAN card is attached, self-attested, and legible.", ["documents"], 0.85, ActionOnFail.auto_reject,
     "PAN card is missing or not clearly attached."),
    ("rule_check_effective_date", "Effective Date Matches Deal ID", "Document Content",
     "Compare agreement effective date with HubSpot onboarding date.", ["documents", "deal.submitted_at"], 0.70, ActionOnFail.flag_review,
     "Effective date on agreement does not match system records."),
    ("rule_check_stamp_duty", "Stamp Duty Compliance", "Document Content",
     "Verify e-stamp certificate is valid and correctly valued.", ["documents", "deal.amount"], 0.75, ActionOnFail.flag_review,
     "Stamp duty certificate is missing or incorrectly valued."),
    ("rule_check_witness_signatures", "Witness Signatures Present", "Document Content",
     "Verify two witnesses are present on execution page.", ["documents"], 0.80, ActionOnFail.flag_review,
     "Witness signatures are missing or incomplete."),
    ("rule_check_company_letterhead", "Company Letterhead & CIN", "Document Content",
     "Verify company letterhead and CIN on cover page.", ["documents"], 0.75, ActionOnFail.warning,
     "Company letterhead or CIN is missing."),
    ("rule_check_contract_term", "Contract Term Within Approved Range", "Document Content",
     "Verify contract term is between 12 and 36 months.", ["documents"], 0.85, ActionOnFail.flag_review,
     "Contract term is outside the approved range."),
    ("rule_check_page_completeness", "All Annexures & Schedules Present", "Document Content",
     "Verify all referenced annexures are attached.", ["documents"], 0.85, ActionOnFail.auto_reject,
     "One or more required annexures are missing from the document bundle."),
    # HubSpot Match
    ("rule_match_pan", "PAN Matches HubSpot Record", "HubSpot Match",
     "Cross-reference PAN from document against HubSpot KYC.", ["documents", "hubspot.pan"], 0.90, ActionOnFail.auto_reject,
     "PAN on document does not match HubSpot record."),
    ("rule_match_amount", "Onboarding Amount Matches HubSpot", "HubSpot Match",
     "Compare contract value against HubSpot deal amount.", ["documents", "deal.amount"], 0.90, ActionOnFail.auto_reject,
     "Contract value does not match HubSpot deal amount."),
    ("rule_match_company_name", "Company Name Matches HubSpot", "HubSpot Match",
     "Match company name from document against HubSpot.", ["documents", "hubspot.company_name"], 0.85, ActionOnFail.flag_review,
     "Company name on document does not match HubSpot after normalisation."),
    ("rule_match_gst", "GST Number Matches HubSpot", "HubSpot Match",
     "Validate GST number and cross-reference with HubSpot.", ["documents", "hubspot.gst"], 0.85, ActionOnFail.auto_reject,
     "GST number mismatch between document and HubSpot."),
    ("rule_match_contact_details", "Contact Details Match HubSpot", "HubSpot Match",
     "Match signatory email and phone against HubSpot contact.", ["documents", "hubspot.contact_email"], 0.75, ActionOnFail.flag_review,
     "Contact details on document differ from HubSpot primary contact."),
    ("rule_match_address", "Registered Address Matches HubSpot", "HubSpot Match",
     "Match registered address from document against HubSpot.", ["documents", "hubspot.billing_address"], 0.80, ActionOnFail.warning,
     "Registered address does not match HubSpot billing address."),
    # Field Completeness
    ("rule_check_required_fields", "All Compulsory HubSpot Fields Filled", "Field Completeness",
     "Check all 14 mandatory HubSpot fields are populated.", ["hubspot.all_fields"], 0.95, ActionOnFail.flag_review,
     "One or more mandatory HubSpot fields are empty."),
    ("rule_check_products_configured", "Products Configured in HubSpot", "Field Completeness",
     "Verify all deal products are active SKUs with correct pricing.", ["hubspot.products"], 0.90, ActionOnFail.flag_review,
     "Products in HubSpot are not correctly configured."),
    ("rule_check_deal_stage", "Deal Stage Valid for Submission", "Field Completeness",
     "Verify deal stage is 'Contract Sent' with valid progression.", ["hubspot.deal_stage"], 0.95, ActionOnFail.flag_review,
     "Deal stage is not valid for submission."),
    ("rule_check_zone_approval", "Zone Manager Approval Recorded", "Field Completeness",
     "Verify Zone Manager approval is recorded in HubSpot.", ["deal.amount", "hubspot.activity_log"], 0.85, ActionOnFail.auto_reject,
     "Zone Manager approval is not recorded for this deal."),
    ("rule_check_onboarding_date", "Onboarding Date Feasibility", "Field Completeness",
     "Check onboarding start date is at least 14 days from submission.", ["deal.submitted_at", "hubspot.onboarding_start_date"], 0.80, ActionOnFail.warning,
     "Onboarding start date is too soon after submission date."),
    ("rule_check_payment_terms", "Payment Terms Standard", "Field Completeness",
     "Verify payment terms are standard (Annual upfront, Net-30).", ["documents"], 0.85, ActionOnFail.flag_review,
     "Non-standard payment terms detected requiring additional approval."),
    # PO Validation
    ("po_rule_linked_deal_exists", "PO is linked to an existing deal", "Deal Linkage",
     "Verify the PO's deal_id references an existing deal in the AR Co-Pilot system.", ["po_data"], 1.0, ActionOnFail.auto_reject,
     "The PO references a deal ID that does not exist — orphan PO."),
    ("po_rule_academic_year_current", "PO academic year matches current cycle", "Deal Linkage",
     "Verify the PO's order_academic_year matches the current active cycle (26-27).", ["po_data"], 1.0, ActionOnFail.auto_reject,
     "PO academic year is not the current cycle (26-27)."),
    ("po_rule_authorized_creator", "PO created by authorized LEAD user", "Authorization",
     "Verify the PO was created by a @leadschool.in email address.", ["po_data"], 1.0, ActionOnFail.auto_reject,
     "PO creator is not a verified LEAD domain user."),
    ("po_rule_finance_approval_aging", "PO is not stuck awaiting Finance approval", "Workflow Health",
     "If the PO is in FIN_HOLD and has been waiting more than 30 minutes, flag it.", ["po_data"], 0.7, ActionOnFail.flag_review,
     "PO has been in FIN_HOLD beyond the acceptable threshold — chase Finance."),
    ("po_rule_customer_verification", "Customer verification link is healthy", "Customer Approval Flow",
     "Verify the customer verification link has been sent and is in a healthy state.", ["po_data"], 0.7, ActionOnFail.flag_review,
     "Customer verification link is missing, inactive, or stalled."),
    ("po_rule_notification_routing", "Notification target matches deal distribution model", "Customer Approval Flow",
     "Verify notification_sent_to (school/distributor) matches the expected distribution model for this deal.", ["po_data"], 0.7, ActionOnFail.flag_review,
     "Notification routing may not match the deal's distribution model."),
    # Policy
    ("rule_check_deviation_approval", "Deviation % Drives ZCEO/Arvind Approval", "Policy",
     "Check if discount >10% has ZCEO approval.", ["deal.amount", "hubspot.list_price", "documents"], 0.88, ActionOnFail.auto_reject,
     "Discount exceeds 10% threshold but ZCEO approval is not attached."),
    ("rule_check_credit_limit", "Customer Credit Limit Check", "Policy",
     "Compare deal value against approved customer credit limit.", ["deal.amount", "hubspot.credit_limit"], 0.85, ActionOnFail.auto_reject,
     "Deal value exceeds customer's approved credit limit."),
    ("rule_check_blacklist", "Entity Not on Restricted Lists", "Policy",
     "Check entity and directors against all restricted-entity lists.", ["deal.customer_name", "hubspot.pan"], 0.99, ActionOnFail.auto_reject,
     "Entity or director found on a restricted list."),
    ("rule_check_regulatory_compliance", "EdTech Regulatory Compliance", "Policy",
     "Verify EdTech regulatory compliance (DPDP, NEP 2020).", ["documents", "deal.products"], 0.85, ActionOnFail.flag_review,
     "Regulatory compliance issue detected."),
    ("rule_check_territory_conflict", "Territory Conflict Check", "Policy",
     "Check for >2 active accounts in same segment-territory.", ["deal.region", "deal.products"], 0.75, ActionOnFail.warning,
     "Territory conflict threshold reached — zone manager sign-off required."),
    ("rule_check_sla_terms", "SLA Terms Within Standard Tier", "Policy",
     "Verify SLA commitment does not exceed product tier standard.", ["documents", "deal.products"], 0.85, ActionOnFail.auto_reject,
     "Above-tier SLA commitment detected without Engineering VP approval."),
]

ALL_RULE_IDS = [r[0] for r in RULES_DATA]

# ---------------------------------------------------------------------------
# Deals
# ---------------------------------------------------------------------------
DEALS_DATA = [
    # DL-12345 — the canonical demo deal with exact 18/5/3 breakdown
    {
        "id": "DL-12345",
        "customer_name": "Scholastic Solutions Pvt Ltd",
        "amount": 3840000.00,
        "status": DealStatus.needs_review,
        "submitted_by_name": "Priya Nair",
        "submitted_by_zone": "West India",
        "submitted_by_avatar_color": "#6366f1",
        "submitted_at": days_ago(1.5),
        "region": "Maharashtra",
        "products": ["Stitch LMS", "Stitch Analytics", "Stitch API"],
        "first_pass_rate": 69,
        "validation_score_passed": 18,
        "validation_score_total": 26,
        "critical_issues_count": 3,
    },
    {
        "id": "DL-12346",
        "customer_name": "Bright Future Academy",
        "amount": 1250000.00,
        "status": DealStatus.auto_approved,
        "submitted_by_name": "Rahul Sharma",
        "submitted_by_zone": "North India",
        "submitted_by_avatar_color": "#8b5cf6",
        "submitted_at": days_ago(0.5),
        "region": "Delhi NCR",
        "products": ["Stitch LMS"],
        "first_pass_rate": 92,
        "validation_score_passed": 24,
        "validation_score_total": 26,
        "critical_issues_count": 0,
    },
    {
        "id": "DL-12347",
        "customer_name": "EduStar Learning Pvt Ltd",
        "amount": 2280000.00,
        "status": DealStatus.auto_rejected,
        "submitted_by_name": "Anjali Desai",
        "submitted_by_zone": "South India",
        "submitted_by_avatar_color": "#ec4899",
        "submitted_at": days_ago(2),
        "region": "Karnataka",
        "products": ["Stitch LMS", "Stitch Analytics"],
        "first_pass_rate": 54,
        "validation_score_passed": 14,
        "validation_score_total": 26,
        "critical_issues_count": 4,
    },
    {
        "id": "DL-12348",
        "customer_name": "Apex International School",
        "amount": 4500000.00,
        "status": DealStatus.needs_review,
        "submitted_by_name": "Vikram Singh",
        "submitted_by_zone": "West India",
        "submitted_by_avatar_color": "#f59e0b",
        "submitted_at": days_ago(3),
        "region": "Gujarat",
        "products": ["Stitch LMS", "Stitch Analytics", "Stitch API", "Stitch HR"],
        "first_pass_rate": 81,
        "validation_score_passed": 21,
        "validation_score_total": 26,
        "critical_issues_count": 1,
    },
    {
        "id": "DL-12349",
        "customer_name": "Sunrise Public School",
        "amount": 980000.00,
        "status": DealStatus.approved,
        "submitted_by_name": "Meera Pillai",
        "submitted_by_zone": "South India",
        "submitted_by_avatar_color": "#10b981",
        "submitted_at": days_ago(5),
        "region": "Kerala",
        "products": ["Stitch LMS"],
        "first_pass_rate": 96,
        "validation_score_passed": 25,
        "validation_score_total": 26,
        "critical_issues_count": 0,
    },
    {
        "id": "DL-12350",
        "customer_name": "Vidya Niketan Trust",
        "amount": 1800000.00,
        "status": DealStatus.stuck,
        "submitted_by_name": "Suresh Patel",
        "submitted_by_zone": "West India",
        "submitted_by_avatar_color": "#3b82f6",
        "submitted_at": days_ago(7),
        "region": "Rajasthan",
        "products": ["Stitch LMS", "Stitch Analytics"],
        "first_pass_rate": 73,
        "validation_score_passed": 19,
        "validation_score_total": 26,
        "critical_issues_count": 2,
    },
    {
        "id": "DL-12351",
        "customer_name": "Greenwood High School",
        "amount": 2100000.00,
        "status": DealStatus.auto_approved,
        "submitted_by_name": "Nita Roy",
        "submitted_by_zone": "East India",
        "submitted_by_avatar_color": "#ef4444",
        "submitted_at": days_ago(1),
        "region": "West Bengal",
        "products": ["Stitch LMS", "Stitch API"],
        "first_pass_rate": 88,
        "validation_score_passed": 23,
        "validation_score_total": 26,
        "critical_issues_count": 0,
    },
    {
        "id": "DL-12352",
        "customer_name": "DPS Premium Network",
        "amount": 6700000.00,
        "status": DealStatus.needs_review,
        "submitted_by_name": "Arjun Kapoor",
        "submitted_by_zone": "North India",
        "submitted_by_avatar_color": "#14b8a6",
        "submitted_at": days_ago(0.8),
        "region": "Delhi NCR",
        "products": ["Stitch LMS", "Stitch Analytics", "Stitch API", "Stitch HR", "Stitch Finance"],
        "first_pass_rate": 76,
        "validation_score_passed": 20,
        "validation_score_total": 26,
        "critical_issues_count": 2,
    },
    {
        "id": "DL-12353",
        "customer_name": "Modern Public School",
        "amount": 1450000.00,
        "status": DealStatus.auto_approved,
        "submitted_by_name": "Divya Menon",
        "submitted_by_zone": "South India",
        "submitted_by_avatar_color": "#6366f1",
        "submitted_at": days_ago(2.5),
        "region": "Tamil Nadu",
        "products": ["Stitch LMS"],
        "first_pass_rate": 91,
        "validation_score_passed": 24,
        "validation_score_total": 26,
        "critical_issues_count": 0,
    },
    {
        "id": "DL-12354",
        "customer_name": "Lotus Valley International",
        "amount": 3200000.00,
        "status": DealStatus.rejected,
        "submitted_by_name": "Priya Nair",
        "submitted_by_zone": "West India",
        "submitted_by_avatar_color": "#6366f1",
        "submitted_at": days_ago(4),
        "region": "Maharashtra",
        "products": ["Stitch LMS", "Stitch Analytics"],
        "first_pass_rate": 58,
        "validation_score_passed": 15,
        "validation_score_total": 26,
        "critical_issues_count": 5,
    },
    {
        "id": "DL-12355",
        "customer_name": "Heritage International School",
        "amount": 1900000.00,
        "status": DealStatus.needs_review,
        "submitted_by_name": "Kavya Reddy",
        "submitted_by_zone": "South India",
        "submitted_by_avatar_color": "#8b5cf6",
        "submitted_at": days_ago(1.2),
        "region": "Telangana",
        "products": ["Stitch LMS", "Stitch Analytics"],
        "first_pass_rate": 84,
        "validation_score_passed": 22,
        "validation_score_total": 26,
        "critical_issues_count": 1,
    },
    {
        "id": "DL-12356",
        "customer_name": "Ryan International Group",
        "amount": 8900000.00,
        "status": DealStatus.stuck,
        "submitted_by_name": "Rohit Gupta",
        "submitted_by_zone": "North India",
        "submitted_by_avatar_color": "#f59e0b",
        "submitted_at": days_ago(6),
        "region": "Maharashtra",
        "products": ["Stitch LMS", "Stitch Analytics", "Stitch API", "Stitch HR"],
        "first_pass_rate": 67,
        "validation_score_passed": 17,
        "validation_score_total": 26,
        "critical_issues_count": 3,
    },
    {
        "id": "DL-12357",
        "customer_name": "Cambridge Foundation School",
        "amount": 2750000.00,
        "status": DealStatus.auto_approved,
        "submitted_by_name": "Sneha Joshi",
        "submitted_by_zone": "West India",
        "submitted_by_avatar_color": "#10b981",
        "submitted_at": days_ago(0.3),
        "region": "Gujarat",
        "products": ["Stitch LMS", "Stitch API"],
        "first_pass_rate": 94,
        "validation_score_passed": 25,
        "validation_score_total": 26,
        "critical_issues_count": 0,
    },
    {
        "id": "DL-12358",
        "customer_name": "Podar International School",
        "amount": 3600000.00,
        "status": DealStatus.needs_review,
        "submitted_by_name": "Aditya Banerjee",
        "submitted_by_zone": "East India",
        "submitted_by_avatar_color": "#3b82f6",
        "submitted_at": days_ago(1.8),
        "region": "West Bengal",
        "products": ["Stitch LMS", "Stitch Analytics", "Stitch API"],
        "first_pass_rate": 79,
        "validation_score_passed": 20,
        "validation_score_total": 26,
        "critical_issues_count": 2,
    },
    {
        "id": "DL-12359",
        "customer_name": "Amity Group of Schools",
        "amount": 12500000.00,
        "status": DealStatus.needs_review,
        "submitted_by_name": "Arjun Kapoor",
        "submitted_by_zone": "North India",
        "submitted_by_avatar_color": "#14b8a6",
        "submitted_at": days_ago(0.6),
        "region": "Delhi NCR",
        "products": ["Stitch LMS", "Stitch Analytics", "Stitch API", "Stitch HR", "Stitch Finance"],
        "first_pass_rate": 71,
        "validation_score_passed": 18,
        "validation_score_total": 26,
        "critical_issues_count": 2,
    },
    {
        "id": "DL-12360",
        "customer_name": "Narayana Educational Trust",
        "amount": 5400000.00,
        "status": DealStatus.auto_approved,
        "submitted_by_name": "Lakshmi Iyer",
        "submitted_by_zone": "South India",
        "submitted_by_avatar_color": "#ef4444",
        "submitted_at": days_ago(1.4),
        "region": "Andhra Pradesh",
        "products": ["Stitch LMS", "Stitch Analytics", "Stitch API"],
        "first_pass_rate": 89,
        "validation_score_passed": 23,
        "validation_score_total": 26,
        "critical_issues_count": 0,
    },
    {
        "id": "DL-12361",
        "customer_name": "Mount Litera Zee School",
        "amount": 1750000.00,
        "status": DealStatus.auto_approved,
        "submitted_by_name": "Priti Shah",
        "submitted_by_zone": "West India",
        "submitted_by_avatar_color": "#6366f1",
        "submitted_at": days_ago(0.2),
        "region": "Maharashtra",
        "products": ["Stitch LMS"],
        "first_pass_rate": 95,
        "validation_score_passed": 25,
        "validation_score_total": 26,
        "critical_issues_count": 0,
    },
    {
        "id": "DL-12362",
        "customer_name": "DAV Public School Network",
        "amount": 7200000.00,
        "status": DealStatus.stuck,
        "submitted_by_name": "Rahul Sharma",
        "submitted_by_zone": "North India",
        "submitted_by_avatar_color": "#8b5cf6",
        "submitted_at": days_ago(8),
        "region": "Punjab",
        "products": ["Stitch LMS", "Stitch Analytics", "Stitch HR"],
        "first_pass_rate": 62,
        "validation_score_passed": 16,
        "validation_score_total": 26,
        "critical_issues_count": 4,
    },
    {
        "id": "DL-12363",
        "customer_name": "K.C. High School & Junior College",
        "amount": 1100000.00,
        "status": DealStatus.approved,
        "submitted_by_name": "Meera Pillai",
        "submitted_by_zone": "South India",
        "submitted_by_avatar_color": "#10b981",
        "submitted_at": days_ago(3.5),
        "region": "Kerala",
        "products": ["Stitch LMS"],
        "first_pass_rate": 97,
        "validation_score_passed": 26,
        "validation_score_total": 26,
        "critical_issues_count": 0,
    },
    {
        "id": "DL-12364",
        "customer_name": "Chitrakoot Edu Foundation",
        "amount": 2600000.00,
        "status": DealStatus.auto_rejected,
        "submitted_by_name": "Vikram Singh",
        "submitted_by_zone": "West India",
        "submitted_by_avatar_color": "#f59e0b",
        "submitted_at": days_ago(4.5),
        "region": "Madhya Pradesh",
        "products": ["Stitch LMS", "Stitch Analytics"],
        "first_pass_rate": 46,
        "validation_score_passed": 12,
        "validation_score_total": 26,
        "critical_issues_count": 6,
    },
]

# ---------------------------------------------------------------------------
# DL-12345 canonical rule results (18 pass, 5 warning, 3 fail)
# ---------------------------------------------------------------------------
DL12345_RULE_RESULTS = {
    "rule_check_signatures": ("pass", 0.97, "All 12 pages carry valid wet-ink signatures. Scholastic Solutions (Rajiv Mehta) and Stitch countersignature (Priya Nair) both present.", "Signature verification complete."),
    "rule_check_pan_attached": ("pass", 0.99, "PAN card AABCS1234P detected. Self-attested, legible, matches HubSpot KYC.", "Direct match confirmed."),
    "rule_check_effective_date": ("warning", 0.62, "Effective date mismatch: Agreement says 12/03/2024, HubSpot records 15/03/2024. Delta is 3 calendar days.", "Discrepancy within tolerance but requires review."),
    "rule_check_stamp_duty": ("pass", 0.91, "E-stamp certificate MH-2024-03781 (₹500) present. Compliant with Maharashtra Stamp Act for this contract value.", "Stamp duty verified."),
    "rule_check_witness_signatures": ("pass", 0.88, "Two witnesses present: Anjali Sharma and Deepak Verma. Both legible with printed names.", "Witness requirement satisfied."),
    "rule_check_company_letterhead": ("pass", 0.93, "Scholastic Solutions Pvt Ltd letterhead on cover page. CIN U80904MH2018PTC312456 matches MCA21.", "Letterhead verified."),
    "rule_check_contract_term": ("pass", 0.95, "Contract term 24 months (01/04/2024 – 31/03/2026) within approved range. Standard renewal clause present.", "Term validated."),
    "rule_check_page_completeness": ("fail", 0.94, "Pricing Annexure missing on Page 4. TOC references Annexure A (Pricing Schedule) but page 4 is blank.", "Critical omission — auto-reject recommended."),
    "rule_match_pan": ("pass", 0.99, "PAN AABCS1234P matches HubSpot KYC exactly.", "Direct match."),
    "rule_match_amount": ("pass", 0.97, "Contract value ₹38,40,000 matches HubSpot Deal Amount exactly.", "Amount consistent."),
    "rule_match_company_name": ("pass", 0.94, "Company name matches HubSpot after normalisation (Pvt→Private, Ltd→Limited).", "Name match confirmed."),
    "rule_match_gst": ("pass", 0.91, "GST 27AABCS1234P1Z5 matches HubSpot. State code 27 (Maharashtra) consistent.", "GSTIN validated."),
    "rule_match_contact_details": ("warning", 0.74, "Email domain discrepancy: agreement uses scholasticsolutions.in vs HubSpot's scholastic-solutions.com. Phone numbers match.", "Email domain mismatch flagged."),
    "rule_match_address": ("pass", 0.89, "Address 302, Andheri East, Mumbai – 400069 matches HubSpot after normalisation.", "Address match confirmed."),
    "rule_check_required_fields": ("pass", 0.98, "All 14 mandatory HubSpot fields populated.", "All fields verified."),
    "rule_check_products_configured": ("pass", 0.96, "3 products configured: Stitch LMS (Enterprise), Stitch Analytics (Pro), Stitch API (Starter). All active SKUs.", "Product config valid."),
    "rule_check_deal_stage": ("pass", 0.99, "Deal stage 'Contract Sent' — correct pre-approval stage. Stage progression is valid.", "Stage validated."),
    "rule_check_zone_approval": ("pass", 0.95, "Zone Manager Priya Nair approval recorded (15/03/2024 11:32 AM). Amount ₹38.4L within ₹50L threshold.", "Approval confirmed."),
    "rule_check_onboarding_date": ("warning", 0.71, "Onboarding date 01/04/2024 is 17 days from submission. Standard is 14 days. 3-day buffer is tight.", "Timeline tight but feasible."),
    "rule_check_payment_terms": ("pass", 0.93, "Payment terms standard: Annual upfront, Net-30 invoice. No deviations.", "Payment terms verified."),
    "rule_check_deviation_approval": ("fail", 0.96, "ZCEO approval email not attached. 15% discount applied exceeds 10% threshold per SALES-POL-004.", "Critical — ZCEO approval required."),
    "rule_check_credit_limit": ("pass", 0.88, "Deal value ₹38.4L within approved credit limit ₹50L. No overdue invoices.", "Credit check passed."),
    "rule_check_blacklist": ("pass", 0.99, "Entity and directors not on any restricted list.", "All lookups clear."),
    "rule_check_regulatory_compliance": ("pass", 0.91, "DPDP Act clauses present (Section 8). No NEP 2020 or coaching centre flags.", "Regulatory sweep passed."),
    "rule_check_territory_conflict": ("warning", 0.68, "3rd active LMS Enterprise account in Mumbai West territory. Zone manager acknowledgement needed.", "Territory conflict flagged."),
    "rule_check_sla_terms": ("fail", 0.93, "SLA 99.9% in agreement exceeds Enterprise Starter standard (99.5%). Engineering VP approval required per ENG-POL-009.", "SLA deviation — approval needed."),
}


async def seed(db: AsyncSession) -> None:
    print("Seeding rules...")
    for rule_data in RULES_DATA:
        rule_id, name, section, prompt, req_ctx, threshold, action_on_fail, error_msg = rule_data
        rule = await db.get(Rule, rule_id)
        if not rule:
            rule = Rule(
                id=rule_id,
                name=name,
                section=section,
                prompt=prompt,
                required_context=req_ctx,
                confidence_threshold=threshold,
                action_on_fail=action_on_fail,
                error_message=error_msg,
                is_active=True,
                fired_count=random.randint(20, 500),
                avg_runtime_ms=random.randint(200, 1200),
            )
            db.add(rule)
    await db.flush()
    print(f"  {len(RULES_DATA)} rules seeded")

    print("Seeding checklists...")
    PO_RULE_IDS = [
        "po_rule_linked_deal_exists",
        "po_rule_academic_year_current",
        "po_rule_authorized_creator",
        "po_rule_finance_approval_aging",
        "po_rule_customer_verification",
        "po_rule_notification_routing",
    ]
    # Deal-validation checklists use random UUIDs; PO checklist uses a fixed ID
    # so the validate endpoint can resolve it by name without a DB lookup.
    po_checklist = await db.get(Checklist, "checklist_po_validation_v1")
    if not po_checklist:
        po_checklist = Checklist(
            id="checklist_po_validation_v1",
            name="PO Validation Checklist",
            version="v1.0",
            status=ChecklistStatus.active,
            rule_ids=PO_RULE_IDS,
            published_at=days_ago(1),
        )
        db.add(po_checklist)
    await db.flush()

    deal_rule_ids = [r[0] for r in RULES_DATA if not r[0].startswith("po_rule_")]
    checklists_data = [
        ("Onboarding Validation", "v3.2", ChecklistStatus.active, deal_rule_ids, days_ago(30)),
        ("Order Approval", "v2.1", ChecklistStatus.active, deal_rule_ids[:18], days_ago(60)),
        ("Renewal Validation", "v1.0", ChecklistStatus.draft, deal_rule_ids[:12], None),
        ("KYC Verification", "v2.4", ChecklistStatus.active, deal_rule_ids[8:18], days_ago(45)),
    ]
    checklist_ids = []
    for name, version, status, rule_ids, published_at in checklists_data:
        cl = Checklist(
            id=str(uuid.uuid4()),
            name=name,
            version=version,
            status=status,
            rule_ids=rule_ids,
            published_at=published_at,
        )
        db.add(cl)
        checklist_ids.append(cl.id)
    await db.flush()
    primary_checklist_id = checklist_ids[0]
    print(f"  5 checklists seeded (primary deal: {primary_checklist_id}, PO: checklist_po_validation_v1)")

    print("Seeding deals...")
    for d in DEALS_DATA:
        existing = await db.get(Deal, d["id"])
        if not existing:
            deal = Deal(**d)
            db.add(deal)
    await db.flush()
    print(f"  {len(DEALS_DATA)} deals seeded")

    print("Seeding validation run for DL-12345 (18/5/3)...")
    run = ValidationRun(
        id=str(uuid.uuid4()),
        deal_id="DL-12345",
        checklist_id=primary_checklist_id,
        status=ValidationRunStatus.completed,
        total_rules=26,
        passed=18,
        warnings=5,
        failed=3,
        started_at=days_ago(1.5) + timedelta(minutes=2),
        completed_at=days_ago(1.5) + timedelta(minutes=12),
    )
    db.add(run)
    await db.flush()

    for rule_id, (status_str, confidence, evidence, reasoning) in DL12345_RULE_RESULTS.items():
        status_map = {"pass": RuleResultStatus.pass_, "warning": RuleResultStatus.warning, "fail": RuleResultStatus.fail}
        rule_instance_info = next((r for r in RULES_DATA if r[0] == rule_id), None)
        rr = RuleResult(
            id=str(uuid.uuid4()),
            validation_run_id=run.id,
            rule_id=rule_id,
            rule_name=rule_instance_info[1] if rule_instance_info else rule_id,
            section=rule_instance_info[2] if rule_instance_info else "Unknown",
            status=status_map[status_str],
            confidence=confidence,
            evidence=evidence,
            ai_reasoning=reasoning,
            action_taken=ActionTaken.none,
            executed_at=days_ago(1.5) + timedelta(minutes=random.uniform(2, 12)),
        )
        db.add(rr)
    await db.flush()
    print("  DL-12345 validation run seeded with 18 pass / 5 warning / 3 fail")

    print("Seeding audit log (30 entries)...")
    actors = [
        (ActorType.user, "Priya Nair"),
        (ActorType.user, "Rahul Sharma"),
        (ActorType.user, "Arjun Kapoor"),
        (ActorType.ai_agent, "Validation Engine"),
        (ActorType.system, "System"),
    ]
    audit_entries = [
        # Deal approvals / rejections
        (days_ago(0.5), ActorType.user, "Rahul Sharma", ActionType.auto_approved, TargetType.deal, "DL-12346", "DL-12346 auto-approved: 24/26 rules passed with no critical failures."),
        (days_ago(0.8), ActorType.ai_agent, "Validation Engine", ActionType.auto_approved, TargetType.deal, "DL-12357", "DL-12357 auto-approved: 25/26 rules passed."),
        (days_ago(1.4), ActorType.ai_agent, "Validation Engine", ActionType.auto_approved, TargetType.deal, "DL-12360", "DL-12360 auto-approved: 23/26 rules passed, no critical failures."),
        (days_ago(0.2), ActorType.ai_agent, "Validation Engine", ActionType.auto_approved, TargetType.deal, "DL-12361", "DL-12361 auto-approved: 25/26 rules passed."),
        (days_ago(2), ActorType.ai_agent, "Validation Engine", ActionType.auto_rejected, TargetType.deal, "DL-12347", "DL-12347 auto-rejected: Contract value mismatch ₹2.28L vs HubSpot ₹2.45L (6.9% deviation)."),
        (days_ago(4.5), ActorType.ai_agent, "Validation Engine", ActionType.auto_rejected, TargetType.deal, "DL-12364", "DL-12364 auto-rejected: 6 critical rule failures including missing PAN and unsigned agreement."),
        (days_ago(4), ActorType.user, "Arjun Kapoor", ActionType.rejected, TargetType.deal, "DL-12354", "DL-12354 manually rejected by Arjun Kapoor: 5 critical failures, entity flagged."),
        (days_ago(5), ActorType.user, "Arjun Kapoor", ActionType.approved, TargetType.deal, "DL-12349", "DL-12349 manually approved by Arjun Kapoor after all issues resolved."),
        (days_ago(3.5), ActorType.user, "Priya Nair", ActionType.approved, TargetType.deal, "DL-12363", "DL-12363 manually approved by Priya Nair: all 26 rules passed."),
        (days_ago(2.5), ActorType.ai_agent, "Validation Engine", ActionType.auto_approved, TargetType.deal, "DL-12353", "DL-12353 auto-approved: 24/26 rules passed."),
        # Rule modifications
        (days_ago(1), ActorType.user, "Arjun Kapoor", ActionType.modified_rule, TargetType.rule, "rule_check_deviation_approval",
         "Confidence threshold updated: 0.85 → 0.88 after 2 false negatives in previous week."),
        (days_ago(2), ActorType.user, "Priya Nair", ActionType.modified_rule, TargetType.rule, "rule_check_effective_date",
         "Action on fail changed: flag_review → warning. Effective date deltas <7 days are common and low risk."),
        (days_ago(3), ActorType.user, "Arjun Kapoor", ActionType.modified_rule, TargetType.rule, "rule_check_sla_terms",
         "Error message updated to include policy reference ENG-POL-009 v2."),
        (days_ago(4), ActorType.user, "Rahul Sharma", ActionType.modified_rule, TargetType.rule, "rule_match_amount",
         "Tolerance threshold updated: 1% → 2% to reduce false positives on GST-inclusive amounts."),
        (days_ago(5), ActorType.user, "Priya Nair", ActionType.modified_rule, TargetType.rule, "rule_check_territory_conflict",
         "Required context expanded to include deal.products for more accurate conflict detection."),
        # Document uploads
        (days_ago(1.5), ActorType.user, "Priya Nair", ActionType.uploaded, TargetType.document, "DL-12345", "Agreement.pdf uploaded for DL-12345 (Scholastic Solutions Pvt Ltd)."),
        (days_ago(1.5), ActorType.user, "Priya Nair", ActionType.uploaded, TargetType.document, "DL-12345", "PAN_Card.pdf uploaded for DL-12345."),
        (days_ago(1.5), ActorType.user, "Priya Nair", ActionType.uploaded, TargetType.document, "DL-12345", "GST_Certificate.pdf uploaded for DL-12345."),
        (days_ago(0.5), ActorType.user, "Rahul Sharma", ActionType.uploaded, TargetType.document, "DL-12346", "Agreement.pdf uploaded for DL-12346 (Bright Future Academy)."),
        (days_ago(0.3), ActorType.user, "Sneha Joshi", ActionType.uploaded, TargetType.document, "DL-12357", "Agreement.pdf uploaded for DL-12357 (Cambridge Foundation School)."),
        # AI pattern detection
        (days_ago(2), ActorType.ai_agent, "Validation Engine", ActionType.pattern_detected, TargetType.deal, "DL-12347",
         "Pattern: amount mismatch >5% detected in 3 deals from South India zone this week. Flagged for zone manager review."),
        (days_ago(3), ActorType.ai_agent, "Validation Engine", ActionType.pattern_detected, TargetType.rule, "rule_check_deviation_approval",
         "Pattern: ZCEO approval missing in 4 of 7 deals with >10% discount this week. Policy enforcement alert raised."),
        (days_ago(5), ActorType.ai_agent, "Validation Engine", ActionType.pattern_detected, TargetType.deal, "DL-12350",
         "Pattern: DL-12350 stuck for 7 days — no reviewer action taken. Escalation triggered."),
        # Overrides
        (days_ago(1), ActorType.user, "Arjun Kapoor", ActionType.override, TargetType.deal, "DL-12355",
         "Rule result override: rule_check_effective_date marked approve_anyway. Reviewer comment: 'Effective date confirmed correct, HubSpot entry was a typo.'"),
        (days_ago(2), ActorType.user, "Priya Nair", ActionType.override, TargetType.deal, "DL-12348",
         "Rule result override: rule_check_territory_conflict marked approve_anyway. Reviewer comment: 'Zone manager has explicitly approved this territory expansion.'"),
        # System events
        (days_ago(0.1), ActorType.system, "System", ActionType.auto_approved, TargetType.deal, "DL-12361",
         "Auto-approval notification sent to Priya Nair for DL-12361."),
        (days_ago(1), ActorType.system, "System", ActionType.pattern_detected, TargetType.checklist, "checklist-onboarding-v32",
         "Checklist 'Onboarding Validation v3.2' — 7-day first-pass rate: 68%. Threshold is 75%. Advisory sent to ops team."),
        (days_ago(3), ActorType.system, "System", ActionType.auto_rejected, TargetType.deal, "DL-12362",
         "Auto-rejection notification sent for DL-12362 (DAV Public School Network). SLA and deviation failures."),
        (days_ago(6), ActorType.system, "System", ActionType.modified_rule, TargetType.checklist, "checklist-order-v21",
         "Checklist 'Order Approval v2.1' auto-archived after new v2.2 published."),
        (days_ago(7), ActorType.system, "System", ActionType.pattern_detected, TargetType.deal, "all",
         "Weekly compliance report generated: 67 deals processed, 89.6% auto-resolution rate, 94.2% compliance score."),
    ]

    for ts, actor_type, actor_name, action_type, target_type, target_id, description in audit_entries:
        entry = AuditLog(
            id=str(uuid.uuid4()),
            timestamp=ts,
            actor_type=actor_type,
            actor_name=actor_name,
            action_type=action_type,
            target_type=target_type,
            target_id=target_id,
            description=description,
        )
        db.add(entry)

    await db.flush()
    print(f"  {len(audit_entries)} audit entries seeded")

    print("Seeding purchase orders (ORP sample data)...")
    # Wipe stale POs so re-seeding always produces a clean state
    from sqlalchemy import delete as sa_delete
    await db.execute(sa_delete(PurchaseOrder))
    await db.flush()

    sample_pos = [
        # ------------------------------------------------------------------ #
        # FIN_APPROVED (8) — finance signed off; some also customer-approved  #
        # ------------------------------------------------------------------ #
        PurchaseOrder(
            order_id="49526",
            deal_id="44452435111",
            customer_name="SRI AMMA DISCOVERY EM SCHOOL",
            agreement_type="PF",
            order_academic_year="26-27",
            order_type=OrderType.forward_counter_hardware,
            created_by="uttam.dey@leadschool.in",
            created_at=datetime(2026, 5, 26, 9, 22),
            po_mode=POMode.online,
            notification_sent_to=NotificationTarget.school,
            current_order_status=OrderStatus.FIN_APPROVED,
            finance_approval_by="hasan.khan@leadschool.in",
            finance_approval_at=datetime(2026, 5, 26, 11, 5),
            approval_aging_minutes=None,
            whatsapp_delivery_status="delivered",
            reminder_count=0,
            po_approved_by="principal.sriamma@gmail.com",
            po_approver_contact_no="9876543210",
            po_approved_on=datetime(2026, 5, 26, 14, 30),
            po_verification_link="https://oc.leadschool.in/poverification?accessCode=A1B2C3",
            po_link_status=POLinkStatus.APPROVED,
        ),
        PurchaseOrder(
            order_id="49510",
            deal_id="45946557006",
            customer_name="ROSE MARY SCHOOL OF EXCELLENCE",
            agreement_type="PF",
            order_academic_year="26-27",
            order_type=OrderType.sampling,
            created_by="siraj.pathan@leadschool.in",
            created_at=datetime(2026, 5, 25, 20, 13),
            po_mode=POMode.online,
            notification_sent_to=NotificationTarget.school,
            current_order_status=OrderStatus.FIN_APPROVED,
            finance_approval_by="vishal.udhani@leadschool.in",
            finance_approval_at=datetime(2026, 5, 25, 22, 45),
            whatsapp_delivery_status="delivered",
            reminder_count=1,
            po_approved_by="director.rosemary@yahoo.com",
            po_approver_contact_no="9845001234",
            po_approved_on=datetime(2026, 5, 26, 9, 10),
            po_verification_link="https://oc.leadschool.in/poverification?accessCode=D4E5F6",
            po_link_status=POLinkStatus.APPROVED,
        ),
        PurchaseOrder(
            order_id="49507",
            deal_id="43170799207",
            customer_name="ROYAL PUBLIC SCHOOL NAWAGARH",
            agreement_type="PF",
            order_academic_year="26-27",
            order_type=OrderType.forward_counter_books,
            created_by="indranil.bhattacharjee@leadschool.in",
            created_at=datetime(2026, 5, 25, 19, 58),
            po_mode=POMode.online,
            notification_sent_to=NotificationTarget.distributor,
            current_order_status=OrderStatus.FIN_APPROVED,
            finance_approval_by="sameera.boyinapalli@leadschool.in",
            finance_approval_at=datetime(2026, 5, 25, 21, 30),
            whatsapp_delivery_status="delivered",
            reminder_count=0,
            po_approved_by="royalpublicschool.nwg@gmail.com",
            po_approver_contact_no="9712334567",
            po_approved_on=datetime(2026, 5, 26, 8, 0),
            po_verification_link="https://oc.leadschool.in/poverification?accessCode=G7H8I9",
            po_link_status=POLinkStatus.APPROVED,
        ),
        PurchaseOrder(
            order_id="49498",
            deal_id="59086467175",
            customer_name="Christhuraja Matric. Hr. Sec School",
            agreement_type="PF",
            order_academic_year="26-27",
            order_type=OrderType.forward,
            created_by="sunita.kumari@leadschool.in",
            created_at=datetime(2026, 5, 25, 14, 45),
            po_mode=POMode.online,
            notification_sent_to=NotificationTarget.school,
            current_order_status=OrderStatus.FIN_APPROVED,
            finance_approval_by="hasan.khan@leadschool.in",
            finance_approval_at=datetime(2026, 5, 25, 17, 0),
            whatsapp_delivery_status="delivered",
            reminder_count=2,
            po_approved_by="christhuraja.admin@gmail.com",
            po_approver_contact_no="9500012345",
            po_approved_on=datetime(2026, 5, 26, 10, 15),
            po_verification_link="https://oc.leadschool.in/poverification?accessCode=J1K2L3",
            po_link_status=POLinkStatus.APPROVED,
        ),
        PurchaseOrder(
            order_id="49485",
            deal_id="61234890123",
            customer_name="AET MATRICULATION HR SEC SCHOOL",
            agreement_type="PF",
            order_academic_year="26-27",
            order_type=OrderType.forward_counter_hardware,
            created_by="rajesh.verma@leadschool.in",
            created_at=datetime(2026, 5, 24, 11, 30),
            po_mode=POMode.offline,
            notification_sent_to=NotificationTarget.school,
            current_order_status=OrderStatus.FIN_APPROVED,
            finance_approval_by="vishal.udhani@leadschool.in",
            finance_approval_at=datetime(2026, 5, 24, 14, 0),
            whatsapp_delivery_status="delivered",
            reminder_count=0,
            po_approved_by="aet.principal@leadschool.in",
            po_approver_contact_no="9381112233",
            po_approved_on=datetime(2026, 5, 24, 16, 45),
            po_verification_link="https://oc.leadschool.in/poverification?accessCode=M4N5O6",
            po_link_status=POLinkStatus.APPROVED,
        ),
        PurchaseOrder(
            order_id="49471",
            deal_id="57823401298",
            customer_name="Yoganathan Selvam- School Sucess Sampling Deal",
            agreement_type="PF",
            order_academic_year="26-27",
            order_type=OrderType.sampling,
            created_by="kavita.sharma@leadschool.in",
            created_at=datetime(2026, 5, 24, 9, 15),
            po_mode=POMode.online,
            notification_sent_to=NotificationTarget.distributor,
            current_order_status=OrderStatus.FIN_APPROVED,
            finance_approval_by="sameera.boyinapalli@leadschool.in",
            finance_approval_at=datetime(2026, 5, 24, 11, 50),
            whatsapp_delivery_status="delivered",
            reminder_count=1,
            po_approved_by="yoganathan.selvam@gmail.com",
            po_approver_contact_no="9944556677",
            po_approved_on=datetime(2026, 5, 24, 15, 20),
            po_verification_link="https://oc.leadschool.in/poverification?accessCode=P7Q8R9",
            po_link_status=POLinkStatus.APPROVED,
        ),
        PurchaseOrder(
            order_id="49460",
            deal_id="48901234567",
            customer_name="Gaurav Dubey- School Sucess Sampling Deal",
            agreement_type="PF",
            order_academic_year="26-27",
            order_type=OrderType.sampling,
            created_by="pradeep.nair@leadschool.in",
            created_at=datetime(2026, 5, 23, 16, 50),
            po_mode=POMode.online,
            notification_sent_to=NotificationTarget.school,
            current_order_status=OrderStatus.FIN_APPROVED,
            finance_approval_by="hasan.khan@leadschool.in",
            finance_approval_at=datetime(2026, 5, 23, 18, 30),
            whatsapp_delivery_status="delivered",
            reminder_count=0,
            po_approved_by="gaurav.dubey@gmail.com",
            po_approver_contact_no="9811223344",
            po_approved_on=datetime(2026, 5, 23, 20, 5),
            po_verification_link="https://oc.leadschool.in/poverification?accessCode=S1T2U3",
            po_link_status=POLinkStatus.APPROVED,
        ),
        PurchaseOrder(
            order_id="49445",
            deal_id="52109876543",
            customer_name="Ronak Jain- Learning System Sampling Deal",
            agreement_type="PF",
            order_academic_year="26-27",
            order_type=OrderType.forward_counter_books,
            created_by="anita.joshi@leadschool.in",
            created_at=datetime(2026, 5, 23, 10, 5),
            po_mode=POMode.offline,
            notification_sent_to=NotificationTarget.school,
            current_order_status=OrderStatus.FIN_APPROVED,
            finance_approval_by="vishal.udhani@leadschool.in",
            finance_approval_at=datetime(2026, 5, 23, 12, 40),
            whatsapp_delivery_status="delivered",
            reminder_count=0,
            po_approved_by="ronak.jain99@yahoo.com",
            po_approver_contact_no="9920112233",
            po_approved_on=datetime(2026, 5, 23, 14, 55),
            po_verification_link="https://oc.leadschool.in/poverification?accessCode=V4W5X6",
            po_link_status=POLinkStatus.APPROVED,
        ),

        # ------------------------------------------------------------------ #
        # FIN_HOLD (3) — waiting on finance; aging tracked                    #
        # ------------------------------------------------------------------ #
        PurchaseOrder(
            order_id="49432",
            deal_id="63458901234",
            customer_name="Ashish Jakhar- Learning System Sampling Deal",
            agreement_type="PF",
            order_academic_year="26-27",
            order_type=OrderType.sampling,
            created_by="uttam.dey@leadschool.in",
            created_at=datetime(2026, 5, 22, 17, 20),
            po_mode=POMode.online,
            notification_sent_to=NotificationTarget.school,
            current_order_status=OrderStatus.FIN_HOLD,
            approval_aging_minutes=3,
            whatsapp_delivery_status="pending",
            reminder_count=0,
        ),
        PurchaseOrder(
            order_id="49418",
            deal_id="46789012345",
            customer_name="SRI AMMA DISCOVERY EM SCHOOL",
            agreement_type="PF",
            order_academic_year="26-27",
            order_type=OrderType.forward_counter_hardware,
            created_by="meera.pillai@leadschool.in",
            created_at=datetime(2026, 5, 22, 8, 40),
            po_mode=POMode.online,
            notification_sent_to=NotificationTarget.distributor,
            current_order_status=OrderStatus.FIN_HOLD,
            approval_aging_minutes=8,
            whatsapp_delivery_status="pending",
            reminder_count=1,
        ),
        PurchaseOrder(
            order_id="49405",
            deal_id="55670123456",
            customer_name="ROSE MARY SCHOOL OF EXCELLENCE",
            agreement_type="PF",
            order_academic_year="26-27",
            order_type=OrderType.forward,
            created_by="suresh.patel@leadschool.in",
            created_at=datetime(2026, 5, 21, 13, 10),
            po_mode=POMode.online,
            notification_sent_to=NotificationTarget.school,
            current_order_status=OrderStatus.FIN_HOLD,
            approval_aging_minutes=25,
            whatsapp_delivery_status="failed",
            reminder_count=3,
        ),

        # ------------------------------------------------------------------ #
        # PO_APPROVAL_PENDING (3) — finance done, awaiting customer action    #
        # ------------------------------------------------------------------ #
        PurchaseOrder(
            order_id="49390",
            deal_id="67890123456",
            customer_name="ROYAL PUBLIC SCHOOL NAWAGARH",
            agreement_type="PF",
            order_academic_year="26-27",
            order_type=OrderType.forward,
            created_by="indranil.bhattacharjee@leadschool.in",
            created_at=datetime(2026, 5, 21, 9, 0),
            po_mode=POMode.online,
            notification_sent_to=NotificationTarget.school,
            current_order_status=OrderStatus.PO_APPROVAL_PENDING,
            finance_approval_by="sameera.boyinapalli@leadschool.in",
            finance_approval_at=datetime(2026, 5, 21, 11, 30),
            whatsapp_delivery_status="delivered",
            reminder_count=1,
            po_verification_link="https://oc.leadschool.in/poverification?accessCode=Y7Z8A9",
            po_link_status=POLinkStatus.ACTIVE,
        ),
        PurchaseOrder(
            order_id="49375",
            deal_id="71234567890",
            customer_name="Christhuraja Matric. Hr. Sec School",
            agreement_type="PF",
            order_academic_year="26-27",
            order_type=OrderType.sampling,
            created_by="kavita.sharma@leadschool.in",
            created_at=datetime(2026, 5, 20, 15, 30),
            po_mode=POMode.online,
            notification_sent_to=NotificationTarget.school,
            current_order_status=OrderStatus.PO_APPROVAL_PENDING,
            finance_approval_by="hasan.khan@leadschool.in",
            finance_approval_at=datetime(2026, 5, 20, 17, 45),
            whatsapp_delivery_status="delivered",
            reminder_count=2,
            po_verification_link="https://oc.leadschool.in/poverification?accessCode=B2C3D4",
            po_link_status=POLinkStatus.ACTIVE,
        ),
        PurchaseOrder(
            order_id="49360",
            deal_id="74567890123",
            customer_name="AET MATRICULATION HR SEC SCHOOL",
            agreement_type="PF",
            order_academic_year="26-27",
            order_type=OrderType.forward_counter_books,
            created_by="rajesh.verma@leadschool.in",
            created_at=datetime(2026, 5, 20, 10, 15),
            po_mode=POMode.offline,
            notification_sent_to=NotificationTarget.distributor,
            current_order_status=OrderStatus.PO_APPROVAL_PENDING,
            finance_approval_by="vishal.udhani@leadschool.in",
            finance_approval_at=datetime(2026, 5, 20, 13, 0),
            whatsapp_delivery_status="delivered",
            reminder_count=0,
            po_verification_link="https://oc.leadschool.in/poverification?accessCode=E5F6G7",
            po_link_status=POLinkStatus.ACTIVE,
        ),

        # ------------------------------------------------------------------ #
        # DRAFT (2) — just created, no approvals yet                         #
        # ------------------------------------------------------------------ #
        PurchaseOrder(
            order_id="49345",
            deal_id="78901234567",
            customer_name="Yoganathan Selvam- School Sucess Sampling Deal",
            agreement_type="PF",
            order_academic_year="26-27",
            order_type=OrderType.sampling,
            created_by="sunita.kumari@leadschool.in",
            created_at=datetime(2026, 5, 27, 8, 5),
            po_mode=POMode.online,
            notification_sent_to=NotificationTarget.school,
            current_order_status=OrderStatus.DRAFT,
            whatsapp_delivery_status=None,
            reminder_count=0,
        ),
        PurchaseOrder(
            order_id="49330",
            deal_id="82345678901",
            customer_name="Gaurav Dubey- School Sucess Sampling Deal",
            agreement_type="PF",
            order_academic_year="26-27",
            order_type=OrderType.forward,
            created_by="pradeep.nair@leadschool.in",
            created_at=datetime(2026, 5, 27, 7, 40),
            po_mode=POMode.online,
            notification_sent_to=NotificationTarget.school,
            current_order_status=OrderStatus.DRAFT,
            whatsapp_delivery_status=None,
            reminder_count=0,
        ),

        # ------------------------------------------------------------------ #
        # DISCARDED (1)                                                       #
        # ------------------------------------------------------------------ #
        PurchaseOrder(
            order_id="49310",
            deal_id="85678901234",
            customer_name="Ronak Jain- Learning System Sampling Deal",
            agreement_type="PF",
            order_academic_year="26-27",
            order_type=OrderType.forward_counter_hardware,
            created_by="anita.joshi@leadschool.in",
            created_at=datetime(2026, 5, 19, 14, 0),
            po_mode=POMode.online,
            notification_sent_to=NotificationTarget.school,
            current_order_status=OrderStatus.DISCARDED,
            finance_approval_by=None,
            whatsapp_delivery_status="failed",
            reminder_count=4,
            po_rejected_at=datetime(2026, 5, 20, 9, 30),
            po_rejection_reason="Duplicate PO — school already approved under order 49310 for same deal.",
        ),

        # ------------------------------------------------------------------ #
        # Edge cases (3) — for validation rule failure demos                 #
        # ------------------------------------------------------------------ #

        # Edge case 1: deal_id has no corresponding deal — "linked deal exists" rule
        PurchaseOrder(
            order_id="49999",
            deal_id="99999999999",
            customer_name="Ashish Jakhar- Learning System Sampling Deal",
            agreement_type="PF",
            order_academic_year="26-27",
            order_type=OrderType.forward,
            created_by="test.orphan@leadschool.in",
            created_at=datetime(2026, 5, 24, 10, 0),
            po_mode=POMode.online,
            notification_sent_to=NotificationTarget.school,
            current_order_status=OrderStatus.FIN_HOLD,
            approval_aging_minutes=120,
            whatsapp_delivery_status="pending",
            reminder_count=0,
        ),

        # Edge case 2: stale academic year — "current academic year" rule
        PurchaseOrder(
            order_id="49888",
            deal_id="44452435111",
            customer_name="SRI AMMA DISCOVERY EM SCHOOL",
            agreement_type="PF",
            order_academic_year="24-25",
            order_type=OrderType.forward,
            created_by="uttam.dey@leadschool.in",
            created_at=datetime(2026, 5, 23, 11, 0),
            po_mode=POMode.online,
            notification_sent_to=NotificationTarget.school,
            current_order_status=OrderStatus.FIN_HOLD,
            approval_aging_minutes=60,
            whatsapp_delivery_status="pending",
            reminder_count=1,
        ),

        # Edge case 3: external email as created_by — "authorized user" rule
        PurchaseOrder(
            order_id="49777",
            deal_id="59086467175",
            customer_name="ROSE MARY SCHOOL OF EXCELLENCE",
            agreement_type="PF",
            order_academic_year="26-27",
            order_type=OrderType.forward,
            created_by="random.person@gmail.com",
            created_at=datetime(2026, 5, 22, 14, 0),
            po_mode=POMode.online,
            notification_sent_to=NotificationTarget.school,
            current_order_status=OrderStatus.DRAFT,
            whatsapp_delivery_status=None,
            reminder_count=0,
        ),
    ]

    for po in sample_pos:
        db.add(po)
    await db.flush()
    n_edge = 3
    print(f"  {len(sample_pos)} purchase orders seeded ({len(sample_pos) - n_edge} live POs, {n_edge} edge cases)")

    await db.commit()
    print("\nSeed complete!")
    print(f"  Deals: {len(DEALS_DATA)}")
    print(f"  Rules: {len(RULES_DATA)} ({len([r for r in RULES_DATA if r[0].startswith('po_rule_')])} PO rules)")
    print("  Checklists: 5 (4 deal + 1 PO validation)")
    print(f"  Purchase orders: {len(sample_pos)}")
    print(f"  Audit entries: {len(audit_entries)}")
    print("  DL-12345 validation run: 18 pass / 5 warning / 3 fail OK")


async def main() -> None:
    await create_tables()
    async with AsyncSessionLocal() as db:
        await seed(db)


if __name__ == "__main__":
    asyncio.run(main())
