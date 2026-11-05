"""Paid-report mission follow-up; staff controls quotations and assignments."""
import frappe

from .api import _enabled, _owned, _safe_paid
from .engine import clean_text


@frappe.whitelist(methods=["POST"])
def request_mission(order_name, mission_type, title, description):
    _enabled()
    order = _owned(order_name)
    if not _safe_paid(order) or order.status != "Delivered":
        frappe.throw("Rapport payé et livré requis.", frappe.PermissionError)
    choices = {"Expert", "Business", "Cyber", "Assistance", "Transformation", "Autre"}
    if mission_type not in choices:
        frappe.throw("Type de mission inconnu.", frappe.ValidationError)
    try:
        title = clean_text(title, 150)
        description = clean_text(description, 2000)
    except ValueError as exc:
        frappe.throw(str(exc), frappe.ValidationError)
    doc = frappe.get_doc({
        "doctype": "SS97 Intelligence Mission", "order": order.name,
        "customer": order.customer, "requested_by": order.requested_by,
        "mission_type": mission_type, "title": title,
        "description": description, "state": "Requested"
    })
    doc.insert(ignore_permissions=True)
    return {"name": doc.name, "state": doc.state, "message": "Demande envoyée à SS97 pour étude et devis."}


@frappe.whitelist(methods=["GET"])
def my_missions(order_name):
    _enabled()
    order = _owned(order_name)
    if not _safe_paid(order):
        frappe.throw("Dossier inaccessible.", frappe.PermissionError)
    return frappe.get_all("SS97 Intelligence Mission",
        filters={"order": order.name, "customer": order.customer,
                 "requested_by": order.requested_by},
        fields=["name", "title", "mission_type", "state", "quotation"],
        order_by="creation desc", limit_page_length=30)
