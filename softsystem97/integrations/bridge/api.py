import json
import uuid

import frappe
from frappe.utils import now_datetime


DOCTYPE = "SS97 Bridge Request"


def _body():
    try:
        data = frappe.request.get_json(silent=True)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def _request_id(data=None, request_id=None, requestId=None):
    data = data or {}
    return (
        requestId
        or request_id
        or data.get("requestId")
        or data.get("RequestId")
        or data.get("request_id")
    )


@frappe.whitelist(allow_guest=True)
def health():
    return {
        "status": "ok",
        "service": "SoftSystem97-Bridge",
        "version": "1.1",
        "timestamp": now_datetime().isoformat()
    }


@frappe.whitelist()
def create_request(
    action=None,
    samAccountName=None,
    displayName=None,
    role=None,
    requestId=None,
    **kwargs
):
    data = _body()

    action = action or data.get("action")
    sam_account_name = (
        samAccountName
        or data.get("samAccountName")
        or data.get("SamAccountName")
    )
    display_name = (
        displayName
        or data.get("displayName")
        or data.get("DisplayName")
    )
    role = role or data.get("role") or data.get("Role")
    request_id = _request_id(data=data, requestId=requestId)

    if not request_id:
        request_id = str(uuid.uuid4())

    if not action:
        frappe.throw("action is required")

    if not sam_account_name:
        frappe.throw("samAccountName is required")

    if not display_name:
        frappe.throw("displayName is required")

    if not role:
        frappe.throw("role is required")

    if frappe.db.exists(DOCTYPE, {"request_id": request_id}):
        return {
            "status": "EXISTS",
            "requestId": request_id
        }

    doc = frappe.get_doc({
        "doctype": DOCTYPE,
        "request_id": request_id,
        "status": "PENDING",
        "action": action,
        "sam_account_name": sam_account_name,
        "display_name": display_name,
        "role": role
    })

    doc.insert(ignore_permissions=True)

    return {
        "status": "PENDING",
        "requestId": request_id
    }


@frappe.whitelist()
def pending():
    rows = frappe.get_all(
        DOCTYPE,
        filters={"status": "PENDING"},
        fields=[
            "request_id",
            "action",
            "sam_account_name",
            "display_name",
            "role",
            "creation"
        ],
        order_by="creation asc",
        limit_page_length=50
    )

    requests = []

    for row in rows:
        requests.append({
            "requestId": row.request_id,
            "action": row.action,
            "payload": {
                "samAccountName": row.sam_account_name,
                "displayName": row.display_name,
                "role": row.role
            }
        })

    return requests


@frappe.whitelist()
def received(requestId=None, request_id=None, **kwargs):
    data = _body()
    rid = _request_id(data, request_id, requestId)

    if not rid:
        frappe.throw("requestId is required")

    name = frappe.db.get_value(
        DOCTYPE,
        {"request_id": rid},
        "name"
    )

    if not name:
        frappe.throw(f"Request not found: {rid}")

    frappe.db.set_value(DOCTYPE, name, "status", "RECEIVED")

    return {
        "status": "RECEIVED",
        "requestId": rid
    }


@frappe.whitelist()
def processing(requestId=None, request_id=None, **kwargs):
    data = _body()
    rid = _request_id(data, request_id, requestId)

    if not rid:
        frappe.throw("requestId is required")

    name = frappe.db.get_value(
        DOCTYPE,
        {"request_id": rid},
        "name"
    )

    if not name:
        frappe.throw(f"Request not found: {rid}")

    frappe.db.set_value(DOCTYPE, name, "status", "PROCESSING")

    return {
        "status": "PROCESSING",
        "requestId": rid
    }


@frappe.whitelist()
def result(requestId=None, request_id=None, **kwargs):
    data = _body()
    rid = _request_id(data, request_id, requestId)

    if not rid:
        frappe.throw("requestId is required")

    name = frappe.db.get_value(
        DOCTYPE,
        {"request_id": rid},
        "name"
    )

    if not name:
        frappe.throw(f"Request not found: {rid}")

    result_status = (
        data.get("Status")
        or data.get("status")
        or "SUCCESS"
    ).upper()

    if result_status not in ("SUCCESS", "ERROR"):
        result_status = "SUCCESS"

    error_message = (
        data.get("Error")
        or data.get("error")
        or data.get("Message")
        or data.get("message")
        or ""
    )

    frappe.db.set_value(
        DOCTYPE,
        name,
        {
            "status": result_status,
            "result_json": json.dumps(
                data,
                ensure_ascii=False,
                default=str
            ),
            "error_message": error_message
        }
    )

    return {
        "status": result_status,
        "requestId": rid
    }
