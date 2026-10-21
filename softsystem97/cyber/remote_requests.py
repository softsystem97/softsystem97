"""Customer-consented management records only. No remote-control transport."""

import frappe

from . import permissions as access


@frappe.whitelist(methods=["POST"])
def request(customer, issue):
    access.require_write_session()
    doc = frappe.get_doc(
        {
            "doctype": "SS97 Cyber Remote Request",
            "customer": customer,
            "issue": issue,
            "state": "Requested",
        }
    ).insert()
    return {"name": doc.name, "state": doc.state, "remote_engine_connected": False}


@frappe.whitelist(methods=["POST"])
def prepare(name, technician, billing_basis, expected_modified, invoice=None):
    access.require_write_session()
    if not access.manager():
        frappe.throw("Cyber management required", frappe.PermissionError)
    doc = frappe.get_doc("SS97 Cyber Remote Request", name)
    doc.check_permission("write")
    doc.modified = expected_modified
    doc.technician, doc.billing_basis, doc.invoice = technician, billing_basis, invoice
    doc.state = "Awaiting consent"
    doc.save()
    return {
        "name": doc.name,
        "state": doc.state,
        "modified": str(doc.modified),
        "can_start": False,
    }


@frappe.whitelist(methods=["POST"])
def transition(name, state, expected_modified, report=None):
    access.require_write_session()
    doc = frappe.get_doc("SS97 Cyber Remote Request", name)
    doc.check_permission("write")
    doc.modified = expected_modified
    doc.state = state
    if report is not None:
        doc.report = report
    doc.save()
    return {
        "name": doc.name,
        "state": doc.state,
        "modified": str(doc.modified),
        "can_start": False,
    }
