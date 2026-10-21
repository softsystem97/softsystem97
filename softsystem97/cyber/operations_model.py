"""Operational Cyber records: scoped, auditable and no remote engine activation."""

from contextlib import contextmanager
from contextvars import ContextVar

import frappe
from frappe.utils import getdate, now_datetime

from . import permissions as access
from .connectors.wazuh import ConnectorError, checked_origin
from .model import CyberDocument

_generated = ContextVar("ss97_cyber_generated", default=False)


@contextmanager
def generated():
    token = _generated.set(True)
    try:
        yield
    finally:
        _generated.reset(token)


class WazuhConfig(CyberDocument):
    def validate(self):
        super().validate()
        if not access.manager():
            frappe.throw("Cyber management required", frappe.PermissionError)
        if self.enabled and not frappe.db.exists(
            "SS97 Cyber Company",
            {
                "customer": self.customer,
                "authorization_status": "Granted",
                "authorization_reference": ["is", "set"],
            },
        ):
            frappe.throw("Company authorization required before enabling Wazuh")
        if type(self.minimum_level) is not int or not 0 <= self.minimum_level <= 16:
            frappe.throw("Wazuh level must be between 0 and 16")
        try:
            checked_origin(
                self.api_url, frappe.conf.get("ss97_wazuh_allowed_hosts") or []
            )
        except ConnectorError:
            frappe.throw("Administrator-approved HTTPS indexer origin required")
        seen = set()
        for row in self.mappings:
            if row.agent_id in seen or not row.agent_id or len(row.agent_id) > 128:
                frappe.throw("Unique bounded Wazuh agent mapping required")
            seen.add(row.agent_id)
            if (
                frappe.db.get_value("SS97 Cyber Asset", row.asset, "customer")
                != self.customer
            ):
                frappe.throw(
                    "Cross-company agent mapping denied", frappe.PermissionError
                )


class GeneratedRecord(CyberDocument):
    def validate(self):
        if not _generated.get() or not self.is_new() or not access.manager():
            frappe.throw(
                "Record generated only by the reviewed server service",
                frappe.PermissionError,
            )
        super().validate()


class SyncEvent(GeneratedRecord):
    pass


class SyncRun(GeneratedRecord):
    pass


class CyberReport(CyberDocument):
    def validate(self):
        super().validate()
        old = self.get_doc_before_save()
        if self.is_new():
            if not _generated.get() or not access.manager() or self.approval != "Draft":
                frappe.throw(
                    "Generate a draft report through the report service",
                    frappe.PermissionError,
                )
            self.approved_by = None
            self.approved_at = None
        else:
            if any(
                old.get(key) != self.get(key)
                for key in ("snapshot", "from_date", "to_date")
            ):
                frappe.throw("Report snapshots are immutable", frappe.PermissionError)
            if old.approval == "Approved" and self.approval != "Approved":
                frappe.throw("Approved report cannot be unapproved")
            if self.approval == "Approved" and old.approval != "Approved":
                if not access.manager():
                    frappe.throw("Cyber management required", frappe.PermissionError)
                self.approved_by = frappe.session.user
                self.approved_at = now_datetime()
            else:
                self.approved_by, self.approved_at = old.approved_by, old.approved_at


def billing_verified(customer, basis, invoice=None):
    company = frappe.get_doc("SS97 Cyber Company", {"customer": customer})
    if (
        company.authorization_status != "Granted"
        or not company.authorization_reference
        or not company.remote_included
    ):
        return False
    if (company.service_start and getdate() < getdate(company.service_start)) or (
        company.service_end and getdate() > getdate(company.service_end)
    ):
        return False
    if basis == "Contract" and company.contract:
        contract = frappe.db.get_value(
            "Contract",
            company.contract,
            ["party_type", "party_name", "status", "start_date", "end_date"],
            as_dict=True,
        )
        return bool(
            contract
            and contract.party_type == "Customer"
            and contract.party_name == customer
            and contract.status == "Active"
            and contract.start_date
            and contract.end_date
            and getdate(contract.start_date) <= getdate() <= getdate(contract.end_date)
        )
    if basis == "Invoice" and invoice:
        row = frappe.db.get_value(
            "Sales Invoice",
            invoice,
            ["customer", "docstatus", "outstanding_amount", "grand_total", "is_return"],
            as_dict=True,
        )
        return bool(
            row
            and row.customer == customer
            and row.docstatus == 1
            and not row.is_return
            and row.grand_total > 0
            and row.outstanding_amount == 0
        )
    return False


class RemoteRequest(CyberDocument):
    def validate(self):
        # Clients may only request/consent/revoke their own preparation records.
        access.require_write_session()
        access.require_customer(self.customer)
        if not frappe.db.exists("SS97 Cyber Company", {"customer": self.customer}):
            frappe.throw("Cyber company enrollment required")
        if frappe.db.get_value("Issue", self.issue, "customer") != self.customer:
            frappe.throw("Issue scope denied", frappe.PermissionError)
        old = self.get_doc_before_save()
        if old and (old.customer != self.customer or old.issue != self.issue):
            frappe.throw("Remote request scope is immutable", frappe.PermissionError)
        is_manager = access.manager()
        is_client = (
            access.CLIENT in access.roles()
            and self.customer == access.client_customer_for_user(frappe.session.user)
        )
        is_tech = (
            self.technician == frappe.session.user
            and self.customer in access.technician_customers()
        )
        if not (is_manager or is_client or is_tech):
            frappe.throw("Remote request actor denied", frappe.PermissionError)
        if (
            self.technician
            and self.state not in ("Revoked", "Declined", "Closed")
            and self.customer not in access.technician_customers(self.technician)
        ):
            frappe.throw("Authorized Cyber technician required", frappe.PermissionError)
        if not old:
            if self.state != "Requested" or (
                not is_manager
                and (self.technician or self.billing_basis or self.invoice)
            ):
                frappe.throw("New request must be unprepared", frappe.PermissionError)
            self.requested_at = now_datetime()
            self.consented_at = self.consented_by = self.closed_at = None
        else:
            self.requested_at = old.requested_at
            self.consented_at, self.consented_by, self.closed_at = (
                old.consented_at,
                old.consented_by,
                old.closed_at,
            )
            if any(
                old.get(key) != self.get(key)
                for key in ("technician", "billing_basis", "invoice")
            ) and (
                not is_manager or old.state not in ("Requested", "Awaiting consent")
            ):
                frappe.throw("Preparation fields locked", frappe.PermissionError)
            allowed = {
                "Requested": {"Awaiting consent", "Revoked", "Closed"},
                "Awaiting consent": {"Consented", "Declined", "Revoked", "Closed"},
                "Consented": {"Revoked", "Closed"},
                "Declined": {"Closed"},
                "Revoked": {"Closed"},
                "Closed": set(),
            }
            if self.state != old.state:
                if self.state not in allowed[old.state]:
                    frappe.throw("Remote request transition denied")
                if self.state in ("Consented", "Declined") and not is_client:
                    frappe.throw(
                        "Only the customer may consent or decline",
                        frappe.PermissionError,
                    )
                if self.state == "Awaiting consent" and (
                    not is_manager
                    or not self.technician
                    or not billing_verified(
                        self.customer, self.billing_basis, self.invoice
                    )
                ):
                    frappe.throw(
                        "Verified scope, billing and technician required",
                        frappe.PermissionError,
                    )
                if self.state == "Consented" and not billing_verified(
                    self.customer, self.billing_basis, self.invoice
                ):
                    frappe.throw(
                        "Billing authorization no longer valid", frappe.PermissionError
                    )
                if self.state == "Closed" and not self.report:
                    frappe.throw("Closing report required")
                if self.state == "Consented":
                    self.consented_at, self.consented_by = (
                        now_datetime(),
                        frappe.session.user,
                    )
                elif self.state == "Closed":
                    self.closed_at = now_datetime()
            else:
                # No silent edit of a consented/closed record by a client.
                if (
                    old.state in ("Consented", "Declined", "Revoked", "Closed")
                    and old.report != self.report
                ):
                    frappe.throw("Use an explicit closure transition")
            if self.state != "Consented":
                self.consented_at, self.consented_by = (
                    old.consented_at,
                    old.consented_by,
                )
            if self.state != "Closed":
                self.closed_at = old.closed_at
        # This is preparation only: no connected engine, no started_at, no billable duration.
        self.duration_seconds = 0
