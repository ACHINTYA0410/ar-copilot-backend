import traceback
from typing import Optional
from fastapi import APIRouter, HTTPException
import mysql.connector

# Import the existing fetch_orders method from the project root
from orp_db import fetch_orders

router = APIRouter()

@router.get("/checklist")
def get_po_validation_checklist(
    order_id: Optional[int] = None,
    agreement_id: Optional[str] = None,
):
    if not order_id and not agreement_id:
        raise HTTPException(status_code=400, detail="Please provide order_id or agreement_id.")
        
    try:
        orders = fetch_orders(order_id=order_id, agreement_id=agreement_id, limit=1)
        if not orders:
            raise HTTPException(status_code=404, detail="No order found.")
            
        order = orders[0]
        
        formatted_order = {
            "deal_id": order.get("Deal Id"),
            "agreement_type": order.get("Agreement Type"),
            "order_id": order.get("Order Id"),
            "academic_year": order.get("Order Academic Year"),
            "order_type": order.get("Order Type"),
            "created_by": order.get("Created By"),
            "created_at": order.get("Created At"),
            "po_mode": order.get("PO Mode"),
            "notification_sent_to": order.get("Notification Sent to"),
            "customer_name": order.get("Customer Name"),
            "po_approved_by": order.get("PO Approved By"),
            "po_approver_contact_no": order.get("PO Approver Contact No"),
            "po_approved_on": order.get("PO Approved On"),
            "po_verification_link": order.get("PO Verification Link"),
            "po_link_status": order.get("PO Link Status"),
            "current_order_status": order.get("Current Order Status"),
            "finance_approval_by": order.get("Finance Approval By"),
            "finance_approval_at": order.get("Finance Approval At"),
            "approval_aging": order.get("Approval Aging"),
            "po_rejected_at": order.get("PO Rejected At"),
            "po_rejection_reasons": order.get("PO Rejection Reasons")
        }

        checklist = []
        
        po_mode = formatted_order.get("po_mode")
        if po_mode:
            checklist.append({
                "key": "po_mode_present",
                "label": "PO mode is available",
                "status": "pass",
                "details": str(po_mode)
            })
        else:
            checklist.append({
                "key": "po_mode_present",
                "label": "PO mode is available",
                "status": "fail",
                "details": "Missing"
            })
            
        cust_name = formatted_order.get("customer_name")
        if cust_name:
            checklist.append({
                "key": "customer_name_present",
                "label": "Customer name is available",
                "status": "pass",
                "details": "Customer name from agreement master"
            })
        else:
            checklist.append({
                "key": "customer_name_present",
                "label": "Customer name is available",
                "status": "fail",
                "details": "Missing customer name"
            })
            
        po_link_status = formatted_order.get("po_link_status")
        if po_link_status == "VERIFIED":
            link_status = "pass"
        elif po_link_status:
            link_status = "warning"
        else:
            link_status = "fail"
            
        checklist.append({
            "key": "po_link_status_valid",
            "label": "PO verification link status is valid",
            "status": link_status,
            "details": po_link_status if po_link_status else "Not available"
        })
        
        order_status = formatted_order.get("current_order_status")
        if order_status:
            checklist.append({
                "key": "approval_status_present",
                "label": "Current order status is available",
                "status": "pass",
                "details": str(order_status)
            })
        else:
            checklist.append({
                "key": "approval_status_present",
                "label": "Current order status is available",
                "status": "fail",
                "details": "Missing order status"
            })
            
        fin_appr_at = formatted_order.get("finance_approval_at")
        if fin_appr_at:
            checklist.append({
                "key": "finance_approval_checked",
                "label": "Finance approval details checked",
                "status": "pass",
                "details": f"Approved by {formatted_order.get('finance_approval_by')} at {fin_appr_at}"
            })
        else:
            checklist.append({
                "key": "finance_approval_checked",
                "label": "Finance approval details checked",
                "status": "warning",
                "details": "Finance approval pending or not available"
            })
            
        po_rej_at = formatted_order.get("po_rejected_at")
        if po_rej_at:
            checklist.append({
                "key": "po_rejection_checked",
                "label": "PO rejection details checked",
                "status": "warning",
                "details": f"Rejected at {po_rej_at} - {formatted_order.get('po_rejection_reasons')}"
            })
        else:
            checklist.append({
                "key": "po_rejection_checked",
                "label": "PO rejection details checked",
                "status": "pass",
                "details": "No rejections found"
            })
            
        summary = {
            "total": len(checklist),
            "passed": sum(1 for c in checklist if c["status"] == "pass"),
            "warnings": sum(1 for c in checklist if c["status"] == "warning"),
            "failed": sum(1 for c in checklist if c["status"] == "fail")
        }
        
        return {
            "order": formatted_order,
            "checklist": checklist,
            "summary": summary
        }
    except HTTPException:
        raise
    except mysql.connector.Error:
        print(f"ORP MySQL error: {traceback.format_exc()}")
        raise HTTPException(
            status_code=503,
            detail="Could not connect to ORP MySQL. Check VPN/network access and try again.",
        )
    except Exception:
        print(f"Error fetching PO validation checklist: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
