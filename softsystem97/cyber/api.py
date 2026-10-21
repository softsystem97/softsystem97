"""Cyber V1 native CRUD helpers. All writes are POST and use document permissions."""

import frappe

from . import permissions as access

FIELDS = {
    "asset": (
        "SS97 Cyber Asset",
        (
            "customer",
            "asset_name",
            "asset_type",
            "operating_system",
            "maintenance_state",
            "backup_state",
            "backup_checked_at",
            "backup_evidence",
        ),
    ),
    "audit": ("SS97 Cyber Audit", ("customer", "title", "asset", "status", "checks")),
    "risk": (
        "SS97 Cyber Risk",
        (
            "customer",
            "title",
            "asset",
            "audit",
            "severity",
            "finding",
            "action_required",
        ),
    ),
    "incident": (
        "SS97 Cyber Incident",
        ("customer", "title", "asset", "issue", "severity", "description"),
    ),
}


@frappe.whitelist(methods=["POST"])
def create_record(kind, values):
    if kind not in FIELDS:
        frappe.throw("Unsupported cyber record")
    values = frappe.parse_json(values) if isinstance(values, str) else values
    dt, fields = FIELDS[kind]
    if not isinstance(values, dict) or set(values) - set(fields):
        frappe.throw("Unsupported cyber fields")
    if kind == "audit" and "checks" in values:
        checks = values["checks"]
        if (
            not isinstance(checks, list)
            or len(checks) > 100
            or any(
                not isinstance(row, dict)
                or set(row) - {"question", "result", "observation"}
                for row in checks
            )
        ):
            frappe.throw("Invalid questionnaire")
    doc = frappe.get_doc(dict(doctype=dt, **values)).insert()
    return {"name": doc.name, "doctype": dt}


@frappe.whitelist(methods=["POST"])
def assign_incident(name, technician, expected_modified):
    if not access.manager():
        frappe.throw("Cyber management required", frappe.PermissionError)
    doc = frappe.get_doc("SS97 Cyber Incident", name)
    doc.check_permission("write")
    # Native optimistic concurrency rejects a stale Desk/API request.
    doc.modified = expected_modified
    doc.assigned_to = technician
    doc.save()
    return {"name": doc.name, "modified": str(doc.modified)}


@frappe.whitelist(methods=["POST"])
def transition_incident(name, status, expected_modified, resolution=None):
    doc = frappe.get_doc("SS97 Cyber Incident", name)
    doc.check_permission("write")
    doc.modified = expected_modified
    doc.status = status
    if resolution is not None:
        doc.resolution = resolution
    doc.save()
    return {"name": doc.name, "status": doc.status, "modified": str(doc.modified)}


@frappe.whitelist()
def dashboard(customer):
    access.require_customer(customer)

    # No broad Customer read permission or duplicate customer table is needed.
    def count(dt, **filters):
        return frappe.db.count(dt, {"customer": customer, **filters})

    backups = {
        state: count("SS97 Cyber Asset", backup_state=state)
        for state in ("Unknown", "Verified", "Failed", "Not applicable")
    }
    return {
        "customer": customer,
        "equipment": count("SS97 Cyber Asset"),
        "completed_audits": count("SS97 Cyber Audit", status="Completed"),
        "open_risks": count("SS97 Cyber Risk", status=["!=", "Resolved"]),
        "critical_incidents": count(
            "SS97 Cyber Incident",
            severity="Critical",
            status=["not in", ["Resolved", "Closed"]],
        ),
        "pending_actions": count(
            "SS97 Cyber Risk", action_required=1, status=["!=", "Resolved"]
        ),
        "backups": backups,
        "backup_verification": "manual evidence only; no automated backup provider connected",
    }
