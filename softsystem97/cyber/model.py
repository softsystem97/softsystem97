"""Native document validation also protects REST writes and linked records."""

import json
from contextvars import ContextVar

import frappe
from frappe.model.document import Document
from frappe.utils import get_datetime, now_datetime

from . import permissions as access

_event_write = ContextVar("ss97_cyber_event_write", default=False)
TRANSITIONS = {
    "Open": {"Investigating"},
    "Investigating": {"Contained", "Resolved"},
    "Contained": {"Investigating", "Resolved"},
    "Resolved": {"Closed", "Investigating"},
    "Closed": set(),
}
RECOMMENDATIONS = {
    "Low": "Plan a corrective action and verify its completion.",
    "Medium": "Assign an owner and prioritize remediation after review.",
    "High": "Review exposure promptly and validate compensating controls.",
    "Critical": "Escalate immediately to the security lead; assess containment with client authorization.",
}


class CyberDocument(Document):
    def validate(self):
        if self.doctype == "SS97 Cyber Event":
            if not _event_write.get():
                frappe.throw(
                    "Audit events are server generated", frappe.PermissionError
                )
            return
        access.require_write_session()
        access.require_customer(self.customer, write=True)
        old = self.get_doc_before_save()
        for field in self.meta.get_table_fields():
            for row in self.get(field.fieldname) or []:
                owner = (
                    frappe.db.get_value(
                        field.options,
                        row.name,
                        ["parent", "parenttype", "parentfield"],
                        as_dict=True,
                    )
                    if row.name
                    else None
                )
                if owner and (
                    owner.parent != self.name
                    or owner.parenttype != self.doctype
                    or owner.parentfield != field.fieldname
                ):
                    frappe.throw(
                        "Child row belongs to another record", frappe.PermissionError
                    )
        if old and old.customer != self.customer:
            frappe.throw("Customer cannot be changed", frappe.PermissionError)
        if self.doctype == "SS97 Cyber Company":
            if not access.manager():
                frappe.throw("Cyber management required", frappe.PermissionError)
            if (
                self.authorization_status == "Granted"
                and not self.authorization_reference
            ):
                frappe.throw("Authorization evidence reference required")
            seen = set()
            for row in self.members:
                if row.user in seen:
                    frappe.throw("Duplicate company member")
                seen.add(row.user)
                if not frappe.db.get_value("User", row.user, "enabled"):
                    frappe.throw("Active member required")
                if (
                    row.responsibility == "Technician"
                    and access.TECH not in access.roles(row.user)
                ):
                    frappe.throw("Cyber technician role required")
            if self.responsible and not frappe.db.get_value(
                "User", self.responsible, "enabled"
            ):
                frappe.throw("Active responsible user required")
            if self.contract and (
                frappe.db.get_value("Contract", self.contract, "party_type")
                != "Customer"
                or frappe.db.get_value("Contract", self.contract, "party_name")
                != self.customer
            ):
                frappe.throw(
                    "Contract does not belong to this customer", frappe.PermissionError
                )
        else:
            if not frappe.db.exists("SS97 Cyber Company", {"customer": self.customer}):
                frappe.throw("Cyber company enrollment required")
        for field, dt in (
            ("asset", "SS97 Cyber Asset"),
            ("audit", "SS97 Cyber Audit"),
            ("issue", "Issue"),
        ):
            value = self.get(field)
            if value and frappe.db.get_value(dt, value, "customer") != self.customer:
                frappe.throw("Cross-company link denied", frappe.PermissionError)
        if (
            self.doctype == "SS97 Cyber Asset"
            and self.backup_state == "Verified"
            and (
                not self.backup_checked_at
                or not self.backup_evidence
                or get_datetime(self.backup_checked_at) > now_datetime()
            )
        ):
            frappe.throw("Dated backup verification evidence required")
        if self.doctype == "SS97 Cyber Audit" and self.status == "Completed":
            if not self.checks or any(
                row.result == "Not checked" for row in self.checks
            ):
                frappe.throw("Complete the audit questionnaire first")
            self.completed_at = (
                old.completed_at
                if old and old.status == "Completed" and old.completed_at
                else now_datetime()
            )
        elif self.doctype == "SS97 Cyber Audit":
            self.completed_at = None
        if self.doctype == "SS97 Cyber Risk":
            if self.severity not in RECOMMENDATIONS:
                frappe.throw("Unsupported severity")
            self.recommendation = RECOMMENDATIONS[self.severity]
        if self.doctype == "SS97 Cyber Incident":
            if old and not access.manager() and old.assigned_to != frappe.session.user:
                frappe.throw(
                    "Assigned incident technician required", frappe.PermissionError
                )
            if old and old.assigned_to != self.assigned_to and not access.manager():
                frappe.throw(
                    "Only cyber management may assign incidents", frappe.PermissionError
                )
            if self.is_new() and self.assigned_to and not access.manager():
                frappe.throw(
                    "Only cyber management may assign incidents", frappe.PermissionError
                )
            if self.assigned_to and (
                access.TECH not in access.roles(self.assigned_to)
                or self.customer not in access.technician_customers(self.assigned_to)
            ):
                frappe.throw(
                    "Assigned technician is not authorized for this company",
                    frappe.PermissionError,
                )
            if (
                old
                and old.status != self.status
                and self.status not in TRANSITIONS[old.status]
            ):
                frappe.throw("Incident transition denied")
            if self.is_new() and self.status != "Open":
                frappe.throw("Incident must start Open")
            if self.status in ("Resolved", "Closed") and not self.resolution:
                frappe.throw("Resolution required")

    def on_update(self):
        if self.doctype == "SS97 Cyber Event":
            return
        old = self.get_doc_before_save()
        changed = [
            df.fieldname
            for df in self.meta.fields
            if df.fieldtype not in ("Section Break", "Column Break")
            and (not old or self.has_value_changed(df.fieldname))
        ]
        token = _event_write.set(True)
        try:
            frappe.get_doc(
                {
                    "doctype": "SS97 Cyber Event",
                    "customer": self.customer,
                    "record_type": self.doctype,
                    "record_name": self.name,
                    "operation": "create" if not old else "update",
                    "actor": frappe.session.user,
                    "changed_fields": json.dumps(changed),
                }
            ).insert(ignore_permissions=True)
        finally:
            _event_write.reset(token)

    def on_trash(self):
        frappe.throw(
            "Cyber records are retained; deletion is disabled", frappe.PermissionError
        )
