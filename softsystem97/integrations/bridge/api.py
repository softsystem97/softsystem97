import frappe
from frappe.utils import now_datetime


@frappe.whitelist(allow_guest=True)
def health():
    return {
        "status": "ok",
        "service": "SoftSystem97-Bridge",
        "version": "1.0",
        "timestamp": now_datetime().isoformat()
    }
