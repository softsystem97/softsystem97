"""Immutable company reports derived only from stored, bounded facts."""

import json

import frappe
from frappe.utils import getdate

from . import permissions as access
from .api import dashboard
from .operations_model import generated


def _rows(dt, filters, fields):
    return frappe.get_all(
        dt,
        filters=filters,
        fields=fields,
        order_by="creation asc",
        limit_page_length=501,
    )


@frappe.whitelist(methods=["POST"])
def generate(customer, from_date, to_date):
    access.require_write_session()
    access.require_customer(customer, write=True)
    if not access.manager():
        frappe.throw("Cyber management required", frappe.PermissionError)
    start, end = getdate(from_date), getdate(to_date)
    if start > end or (end - start).days > 366:
        frappe.throw("Report period must be ordered and at most 367 days")
    if not frappe.db.exists("SS97 Cyber Company", {"customer": customer}):
        frappe.throw("Cyber enrollment required")
    # State inventories reflect generation time; events/audits reflect the requested period.
    state = {"customer": customer}
    period = {
        "customer": customer,
        "creation": [
            "between",
            [str(start) + " 00:00:00", str(end) + " 23:59:59.999999"],
        ],
    }
    sections = {
        "equipment": _rows(
            "SS97 Cyber Asset",
            state,
            [
                "name",
                "asset_name",
                "asset_type",
                "maintenance_state",
                "backup_state",
                "backup_checked_at",
                "backup_evidence",
            ],
        ),
        "audits": _rows(
            "SS97 Cyber Audit", period, ["name", "title", "status", "completed_at"]
        ),
        "risks": _rows(
            "SS97 Cyber Risk",
            state,
            [
                "name",
                "title",
                "risk_kind",
                "severity",
                "status",
                "recommendation",
                "assigned_to",
                "due_date",
            ],
        ),
        "incidents": _rows(
            "SS97 Cyber Incident",
            period,
            ["name", "title", "severity", "status", "resolution"],
        ),
    }
    last_import = frappe.get_all(
        "SS97 Cyber Sync Run",
        filters={"customer": customer},
        fields=["creation", "status", "truncated"],
        order_by="creation desc",
        limit_page_length=1,
    )
    monitoring = (
        "No Wazuh import recorded; no continuous coverage verified"
        if not last_import
        else f"Last Wazuh import: {last_import[0].status} at {last_import[0].creation}; "
        f"truncated={bool(last_import[0].truncated)}; no continuous coverage verified"
    )
    snapshot = {
        "customer": customer,
        "from_date": str(start),
        "to_date": str(end),
        "generated_at": str(frappe.utils.now_datetime()),
        "indicators": dashboard(customer),
        "sections": {key: rows[:500] for key, rows in sections.items()},
        "truncated": {key: len(rows) > 500 for key, rows in sections.items()},
        "known_protection": "Unknown: no EDR provider connected",
        "monitoring": monitoring,
        "limits": [
            "Equipment, risks and KPIs are current snapshots, not historical state reconstruction",
            "Audit/incident lists include records created in the requested period",
            "Manual evidence only for backup verification; no remote assessment performed",
            "Vulnerabilities are manually classified risks, not results of an automatic scan",
        ],
    }
    with generated():
        doc = frappe.get_doc(
            {
                "doctype": "SS97 Cyber Report",
                "customer": customer,
                "from_date": start,
                "to_date": end,
                "approval": "Draft",
                "snapshot": json.dumps(snapshot, default=str),
            }
        ).insert(ignore_permissions=True)
    return {"name": doc.name, "approval": doc.approval}


@frappe.whitelist(methods=["POST"])
def approve(name, expected_modified):
    access.require_write_session()
    if not access.manager():
        frappe.throw("Cyber management required", frappe.PermissionError)
    doc = frappe.get_doc("SS97 Cyber Report", name)
    doc.check_permission("write")
    doc.modified = expected_modified
    doc.approval = "Approved"
    doc.save()
    return {"name": doc.name, "approval": doc.approval}


@frappe.whitelist()
def detail(name):
    doc = frappe.get_doc("SS97 Cyber Report", name)
    doc.check_permission("read")
    access.require_customer(doc.customer)
    return {
        "name": doc.name,
        "approval": doc.approval,
        "data": json.loads(doc.snapshot),
    }
