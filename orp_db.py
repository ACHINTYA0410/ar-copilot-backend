import os
from pathlib import Path
import mysql.connector
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

def get_orp_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_MYSQL_HOST"),
        port=int(os.getenv("DB_MYSQL_PORT", "3306")),
        user=os.getenv("DB_MYSQL_USER"),
        password=os.getenv("DB_MYSQL_PASSWORD"),
        database=os.getenv("DB_MYSQL_DB_NAME"),
        connection_timeout=10,
    )
    


def fetch_orders(order_id=None, agreement_id=None, order_status=None, po_mode=None, limit=50):
    limit = min(int(limit), 500)

    query = """
    SELECT
        oh.agreement_id AS `Deal Id`,
        am.agreement_type AS `Agreement Type`,
        oh.id AS `Order Id`,
        oh.academic_year AS `Order Academic Year`,
        ot.name AS `Order Type`,
        u.email AS `Created By`,
        oh.created_at AS `Created At`,
        CASE WHEN opv.id IS NOT NULL THEN 'Online' ELSE 'Offline' END AS `PO Mode`,
        CASE WHEN am.cp_type IS NOT NULL THEN am.cp_type ELSE 'School' END AS `Notification Sent to`,
        am.customer_name AS `Customer Name`,
        opv.email AS `PO Approved By`,
        opv.phone_number AS `PO Approver Contact No`,
        fwa2.created_at AS `PO Approved On`,
        as2.access_link AS `PO Verification Link`,
        as2.status AS `PO Link Status`,
        oh.status AS `Current Order Status`,
        fwa.created_by AS `Finance Approval By`,
        fwa.created_at AS `Finance Approval At`,
        CONCAT(
            TIMESTAMPDIFF(HOUR, fwa4.created_at, fwa5.created_at), ' hours ',
            MOD(TIMESTAMPDIFF(MINUTE, fwa4.created_at, fwa5.created_at), 60), ' minutes'
        ) AS `Approval Aging`,
        opv.phone_number AS `Whatsapp Delivery Status`,
        opv.phone_number AS `Reminder Details`,
        fwa3.created_at AS `PO Rejected At`,
        fwa3.remarks AS `PO Rejection Reasons`
    FROM order_hdr oh
    LEFT JOIN order_type ot ON ot.id = oh.order_type_id
    LEFT JOIN order_workflow_log fwa ON oh.id = fwa.order_id AND fwa.to_status = 'FIN_APPROVED'
    LEFT JOIN order_workflow_log fwa2 ON oh.id = fwa2.order_id
        AND fwa2.from_status = 'PO_APPROVAL_PENDING'
        AND (fwa2.to_status = 'FIN_PENDING' OR fwa2.to_status = 'QC_PENDING')
    LEFT JOIN order_workflow_log fwa3 ON oh.id = fwa3.order_id AND fwa3.to_status = 'PO_REJECTED'
    LEFT JOIN order_workflow_log fwa4 ON oh.id = fwa4.order_id AND fwa4.from_status = 'DRAFT'
    LEFT JOIN order_workflow_log fwa5 ON oh.id = fwa5.order_id AND fwa5.to_status = 'FIN_PENDING'
    LEFT JOIN agreement_master am ON am.id = oh.agreement_id
    LEFT JOIN order_po_verification opv ON oh.id = opv.order_id AND opv.is_active = true
    LEFT JOIN authentication_store as2 ON as2.id = (
        SELECT MAX(id)
        FROM authentication_store
        WHERE order_id = oh.id AND access_type = 'LINK'
    )
    LEFT JOIN users u ON u.id = oh.created_by
    WHERE oh.academic_year IN ('25-26', '26-27')
      AND ot.id NOT IN (7,8,9,14,15,16)
    """

    params = []

    if order_id:
        query += " AND oh.id = %s"
        params.append(order_id)

    if agreement_id:
        query += " AND oh.agreement_id = %s"
        params.append(agreement_id)

    if order_status:
        query += " AND oh.status = %s"
        params.append(order_status)

    if po_mode == "Online":
        query += " AND opv.id IS NOT NULL"
    elif po_mode == "Offline":
        query += " AND opv.id IS NULL"

    query += " ORDER BY oh.created_at DESC LIMIT %s"
    params.append(limit)

    conn = get_orp_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, params)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()
