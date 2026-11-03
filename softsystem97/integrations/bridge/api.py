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


@frappe.whitelist(methods=["POST"])
def create_request(
    action=None,
    samAccountName=None,
    displayName=None,
    role=None,
    requestId=None,
    **kwargs
):
    frappe.has_permission(DOCTYPE, "create", throw=True)
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
        _get_request(request_id)
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

    doc.insert()

    return {
        "status": "PENDING",
        "requestId": request_id
    }


@frappe.whitelist()
def pending():
    frappe.has_permission(DOCTYPE, "read", throw=True)
    rows = frappe.get_list(
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


def _get_request(request_id):
    frappe.has_permission(DOCTYPE, "read", throw=True)
    if not request_id:
        frappe.throw("requestId is required")
    doc = frappe.get_doc(DOCTYPE, {"request_id": request_id})
    doc.check_permission("read")
    return doc


@frappe.whitelist(methods=["POST"])
def received(requestId=None, request_id=None, **kwargs):
    data = _body()
    rid = _request_id(data, request_id, requestId)

    doc = _get_request(rid)
    doc.status = "RECEIVED"
    doc.save()

    return {
        "status": "RECEIVED",
        "requestId": rid
    }


@frappe.whitelist(methods=["POST"])
def processing(requestId=None, request_id=None, **kwargs):
    data = _body()
    rid = _request_id(data, request_id, requestId)

    doc = _get_request(rid)
    doc.status = "PROCESSING"
    doc.save()

    return {
        "status": "PROCESSING",
        "requestId": rid
    }


@frappe.whitelist(methods=["POST"])
def result(requestId=None, request_id=None, **kwargs):
    data = _body()
    rid = _request_id(data, request_id, requestId)

    doc = _get_request(rid)
    doc.check_permission("write")

    result_status = data.get("Status", data.get("status", "SUCCESS"))

    if not isinstance(result_status, str) or result_status.upper() not in ("SUCCESS", "ERROR"):
        frappe.throw("status must be SUCCESS or ERROR")
    result_status = result_status.upper()

    error_message = (
        data.get("Error")
        or data.get("error")
        or data.get("Message")
        or data.get("message")
        or ""
    )

    doc.update(
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
    doc.save()

    return {
        "status": result_status,
        "requestId": rid
    }
