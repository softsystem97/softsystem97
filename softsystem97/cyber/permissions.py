"""Shared REST, Desk, document and API authorization; no browser trust."""

import frappe

from softsystem97.integrations.ticket_bridge.policy import client_customer_for_user

DIRECTORS = {"SS97 Cyber Direction", "SS97 Cyber Manager"}
TECH = "SS97 Cyber Technician"
CLIENT = "SS97 Cyber Client"
DOCTYPES = (
    "SS97 Cyber Company",
    "SS97 Cyber Asset",
    "SS97 Cyber Audit",
    "SS97 Cyber Risk",
    "SS97 Cyber Incident",
    "SS97 Cyber Event",
    "SS97 Cyber Wazuh Config",
    "SS97 Cyber Sync Event",
    "SS97 Cyber Sync Run",
    "SS97 Cyber Report",
    "SS97 Cyber Remote Request",
)


def roles(user=None):
    user = user or frappe.session.user
    if not user or user == "Guest" or not frappe.db.get_value("User", user, "enabled"):
        return set()
    return {
        role
        for role in frappe.get_roles(user)
        if frappe.db.exists("Role", {"name": role, "disabled": 0})
    }


def manager(user=None):
    return (
        bool(roles(user) & DIRECTORS)
        or (user or frappe.session.user) == "Administrator"
    )


def technician_customers(user=None):
    user = user or frappe.session.user
    if TECH not in roles(user):
        return set()
    companies = frappe.get_all(
        "SS97 Cyber Member",
        filters={
            "user": user,
            "parenttype": "SS97 Cyber Company",
            "parentfield": "members",
            "responsibility": "Technician",
        },
        pluck="parent",
    )
    return (
        set(
            frappe.get_all(
                "SS97 Cyber Company",
                filters={"name": ["in", companies]},
                pluck="customer",
            )
        )
        if companies
        else set()
    )


def customers(user=None):
    user = user or frappe.session.user
    result = technician_customers(user)
    if CLIENT in roles(user):
        customer = client_customer_for_user(user)
        if customer:
            result.add(customer)
    return result


def require_customer(customer, write=False):
    current = roles()
    if not (current or frappe.session.user == "Administrator"):
        frappe.throw("Active cyber session required", frappe.PermissionError)
    if not frappe.db.exists("Customer", {"name": customer, "disabled": 0}):
        frappe.throw("Cyber scope denied", frappe.PermissionError)
    if manager():
        return
    if customer not in customers() or (
        write and customer not in technician_customers()
    ):
        frappe.throw("Cyber scope denied", frappe.PermissionError)


def has_permission(doc, user=None, permission_type=None, **kwargs):
    if manager(user):
        return True
    if doc.doctype in ("SS97 Cyber Wazuh Config", "SS97 Cyber Sync Run"):
        return False
    if doc.customer not in customers(user):
        return False
    kind = permission_type or kwargs.get("ptype") or "read"
    if doc.doctype == "SS97 Cyber Report":
        return kind in ("read", "select") and (
            doc.approval == "Approved" or doc.customer in technician_customers(user)
        )
    if doc.doctype == "SS97 Cyber Remote Request":
        return kind in ("read", "select", "create", "write")
    if doc.doctype == "SS97 Cyber Sync Event":
        return kind in ("read", "select")
    if kind in ("read", "select"):
        return True
    if (
        doc.doctype == "SS97 Cyber Incident"
        and kind == "write"
        and doc.assigned_to != (user or frappe.session.user)
    ):
        return False
    if (
        doc.doctype == "SS97 Cyber Risk"
        and kind == "write"
        and doc.assigned_to
        and doc.assigned_to != (user or frappe.session.user)
    ):
        return False
    return (
        doc.customer in technician_customers(user)
        and doc.doctype not in ("SS97 Cyber Company", "SS97 Cyber Event")
        and kind in ("create", "write")
    )


def query_conditions(user=None, doctype=None):
    # Each hook binds a fixed DocType; no table name comes from an HTTP argument.
    if manager(user):
        return ""
    if doctype in ("SS97 Cyber Wazuh Config", "SS97 Cyber Sync Run"):
        return "1=0"
    values = customers(user)
    if not values:
        return "1=0"
    clause = (
        "`tab"
        + doctype
        + "`.customer in ("
        + ",".join(frappe.db.escape(v) for v in values)
        + ")"
    )
    if doctype == "SS97 Cyber Report":
        tech = technician_customers(user)
        approved = "`tabSS97 Cyber Report`.approval='Approved'"
        if tech:
            approved += (
                " or `tabSS97 Cyber Report`.customer in ("
                + ",".join(frappe.db.escape(v) for v in tech)
                + ")"
            )
        clause += " and (" + approved + ")"
    return clause


def company_query(user=None):
    return query_conditions(user, "SS97 Cyber Company")


def asset_query(user=None):
    return query_conditions(user, "SS97 Cyber Asset")


def audit_query(user=None):
    return query_conditions(user, "SS97 Cyber Audit")


def risk_query(user=None):
    return query_conditions(user, "SS97 Cyber Risk")


def incident_query(user=None):
    return query_conditions(user, "SS97 Cyber Incident")


def event_query(user=None):
    return query_conditions(user, "SS97 Cyber Event")


def require_write_session():
    """Protect native REST too when a fresh browser session has no CSRF yet."""
    import hmac

    request = getattr(frappe.local, "request", None)
    if request is None:
        return  # Trusted server-side document operation, not an HTTP endpoint.
    saved = frappe.session.data.get("csrf_token")
    supplied = frappe.get_request_header("X-Frappe-CSRF-Token") or frappe.form_dict.get(
        "csrf_token"
    )
    if (
        request.method not in ("POST", "PUT", "PATCH")
        or not isinstance(saved, str)
        or not saved
        or not isinstance(supplied, str)
        or not hmac.compare_digest(saved, supplied)
    ):
        frappe.throw("Cyber write requires native session CSRF", frappe.PermissionError)


def wazuh_config_query(user=None):
    return query_conditions(user, "SS97 Cyber Wazuh Config")


def sync_event_query(user=None):
    return query_conditions(user, "SS97 Cyber Sync Event")


def sync_run_query(user=None):
    return query_conditions(user, "SS97 Cyber Sync Run")


def report_query(user=None):
    return query_conditions(user, "SS97 Cyber Report")


def remote_request_query(user=None):
    return query_conditions(user, "SS97 Cyber Remote Request")
