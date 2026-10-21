"""Role-specific scoped workspaces, projections only; no credentials or broad Customer listing."""

import frappe

from . import permissions as access

VIEWS = {
    "direction": "SS97 Cyber Direction",
    "manager": "SS97 Cyber Manager",
    "technician": access.TECH,
    "client": access.CLIENT,
}
TABLES = {
    "assets": (
        "SS97 Cyber Asset",
        [
            "name",
            "customer",
            "asset_name",
            "asset_type",
            "maintenance_state",
            "backup_state",
        ],
    ),
    "audits": (
        "SS97 Cyber Audit",
        ["name", "customer", "title", "status", "completed_at"],
    ),
    "risks": (
        "SS97 Cyber Risk",
        ["name", "customer", "title", "severity", "status", "assigned_to", "due_date"],
    ),
    "incidents": (
        "SS97 Cyber Incident",
        ["name", "customer", "title", "severity", "status", "assigned_to"],
    ),
    "reports": (
        "SS97 Cyber Report",
        ["name", "customer", "from_date", "to_date", "approval", "modified"],
    ),
    "assistance": (
        "SS97 Cyber Remote Request",
        [
            "name",
            "customer",
            "issue",
            "state",
            "technician",
            "duration_seconds",
            "billing_basis",
            "modified",
        ],
    ),
}


@frappe.whitelist()
def available_views():
    current = access.roles()
    return [
        name
        for name, role in VIEWS.items()
        if role in current or frappe.session.user == "Administrator"
    ]


def _scope(view):
    if view not in available_views():
        frappe.throw("Cyber workspace role denied", frappe.PermissionError)
    if view in ("direction", "manager"):
        rows = frappe.get_all(
            "SS97 Cyber Company", fields=["customer"], limit_page_length=5001
        )
        return {row.customer for row in rows[:5000]}, len(rows) > 5000
    if view == "technician":
        return access.technician_customers(), False
    value = access.client_customer_for_user(frappe.session.user)
    return ({value} if value else set()), False


@frappe.whitelist()
def load(view, customer=None):
    scope, truncated = _scope(view)
    if customer:
        if customer not in scope:
            frappe.throw("Cyber workspace scope denied", frappe.PermissionError)
        scope = {customer}
    companies = []
    for row in (
        frappe.get_all(
            "SS97 Cyber Company",
            filters={"customer": ["in", sorted(scope)]},
            fields=[
                "customer",
                "contract",
                "plan",
                "service_start",
                "service_end",
                "service_scope",
                "included_services",
            ],
            order_by="customer asc",
            limit_page_length=50,
        )
        if scope
        else []
    ):
        row["contract_status"] = (
            frappe.db.get_value("Contract", row.contract, "status")
            if row.contract
            else "Not configured"
        )
        companies.append(row)
    filters = {"customer": ["in", sorted(scope)]}
    totals = {
        key: 0
        for key in (
            "equipment",
            "completed_audits",
            "open_risks",
            "critical_incidents",
            "pending_actions",
            "open_incidents",
            "alerts",
            "active_contracts",
            "open_vulnerabilities",
            "urgent_actions",
        )
    }
    if scope:
        specs = {
            "equipment": ("SS97 Cyber Asset", {}),
            "completed_audits": ("SS97 Cyber Audit", {"status": "Completed"}),
            "open_risks": ("SS97 Cyber Risk", {"status": ["!=", "Resolved"]}),
            "critical_incidents": (
                "SS97 Cyber Incident",
                {"severity": "Critical", "status": ["not in", ["Resolved", "Closed"]]},
            ),
            "pending_actions": (
                "SS97 Cyber Risk",
                {"action_required": 1, "status": ["!=", "Resolved"]},
            ),
            "open_incidents": (
                "SS97 Cyber Incident",
                {"status": ["not in", ["Resolved", "Closed"]]},
            ),
            "alerts": ("SS97 Cyber Sync Event", {}),
            "urgent_actions": (
                "SS97 Cyber Risk",
                {
                    "severity": ["in", ["High", "Critical"]],
                    "action_required": 1,
                    "status": ["!=", "Resolved"],
                },
            ),
            "open_vulnerabilities": (
                "SS97 Cyber Risk",
                {"risk_kind": "Vulnerability", "status": ["!=", "Resolved"]},
            ),
        }
        for key, (dt, extra) in specs.items():
            totals[key] = frappe.db.count(dt, {**filters, **extra})
        contract_refs = frappe.get_all(
            "SS97 Cyber Company",
            filters={**filters, "contract": ["is", "set"]},
            pluck="contract",
        )
        totals["active_contracts"] = (
            frappe.db.count(
                "Contract",
                {
                    "name": ["in", contract_refs],
                    "party_type": "Customer",
                    "party_name": ["in", sorted(scope)],
                    "status": "Active",
                    "start_date": ["<=", frappe.utils.today()],
                    "end_date": [">=", frappe.utils.today()],
                },
            )
            if contract_refs
            else 0
        )
    tables = {}
    for key, (dt, fields) in TABLES.items():
        query = dict(filters)
        if view == "technician" and key in ("incidents", "risks"):
            query["assigned_to"] = frappe.session.user
        if view == "client" and key == "reports":
            query["approval"] = "Approved"
        tables[key] = (
            frappe.get_list(
                dt,
                filters=query,
                fields=fields,
                order_by="modified desc",
                limit_page_length=50,
            )
            if scope
            else []
        )
    return {
        "view": view,
        "companies": companies,
        "indicators": totals,
        "tables": tables,
        "scope_truncated": truncated,
        "table_limit": 50,
        "remote_engine_connected": False,
        "edr_protection": "Unknown: no provider connected",
        "monitoring": "Only imported indexer events are counted; no continuous coverage inferred",
        "subscription_billing": "Contract metadata only; no subscription or charging engine enabled",
    }
