"""Private metadata-only inventory. No renderer, business records or source export."""

import hashlib
import hmac
import re
import secrets
from importlib import metadata
from pathlib import Path

import frappe

ROUTES = (
    "espace-technicien",
    "espace-technicien/tickets",
    "espace-client",
    "espace-client/ticket",
)
ISSUE_FIELDS = (
    "ss97_technician",
    "status",
    "customer",
    "priority",
    "issue_type",
    "ss97_contact_email",
    "ss97_public_ref",
    "ss97_ticket_status",
    "ss97_payment_status",
    "ss97_payment_ref",
    "ss97_invoice_amount",
    "ss97_contract_ref",
    "ss97_stripe_checkout_url",
    "ss97_category",
    "ss97_source",
    "ss97_device_summary",
    "ss97_appointment_on",
    "ss97_intervention_started_on",
    "ss97_resolved_on",
    "ss97_intervention_report",
    "ss97_intervention_address",
)
INVOICE_FIELDS = (
    "ss97_stripe_session_id",
    "ss97_stripe_payment_intent",
    "ss97_stripe_mode",
    "ss97_receipt_ref",
    "ss97_paid_on",
    "ss97_payment_status",
    "ss97_stripe_subscription_id",
)
CUSTOMER_FIELDS = ("ss97_stripe_customer_id", "ss97_stripe_subscription_id")
API_METHODS = (
    "ss97_client_ticket_api",
    "ss97_ticket_confirm_payment",
    "ss97_ticket_public_detail",
    "ss97_ticket_public_message",
    "ss97_ai_agent_dialogue_turn",
)
PUBLIC_KEYS = frozenset(
    (
        "format",
        "executed_route",
        "source_exported",
        "routes",
        "apps",
        "app",
        "version",
        "route_file_candidates",
        "path",
        "sha256",
        "inspection",
        "hooks",
        "web_pages",
        "name",
        "route",
        "published",
        "content_type",
        "issue_fields",
        "fieldtype",
        "options",
        "permlevel",
        "read_only",
        "reqd",
        "issue_permissions",
        "custom_permissions",
        "role",
        "read",
        "write",
        "create",
        "delete",
        "submit",
        "cancel",
        "if_owner",
        "technician_roles",
        "disabled",
        "desk_access",
        "workflows",
        "active",
        "state_field",
        "states",
        "state",
        "doc_status",
        "allow_edit",
        "transitions",
        "action",
        "next_state",
        "allowed",
        "has_private_condition",
        "issue_server_scripts",
        "script_type",
        "doctype_event",
        "rewrite_rule_count",
        "website_path_resolver",
        "page_renderer",
        "permission_query_conditions",
        "has_permission",
        "doc_events",
        "Issue",
        "*",
        "client_scripts",
        "dt",
        "enabled",
        "view",
        "api_scripts",
        "api_method",
        "allow_guest",
        "required_doctypes",
        "exists",
        "reference_records",
        "issue_priority",
        "support_type",
        "property_setter_count",
        "assignment_rules",
        "property_setters",
        "document_type",
        "rule",
        "field",
        "doc_type",
        "field_name",
        "doctype_or_field",
        "property",
        "property_type",
        "custom_field_count",
        "user_permission_count",
        "privacy",
        "pseudonymized",
        "aliases_stable_across_reports",
        "limits",
        "invoice_fields",
        "customer_fields",
        *ISSUE_FIELDS,
        *INVOICE_FIELDS,
        *CUSTOMER_FIELDS,
        *API_METHODS,
    )
)
PUBLIC_VALUES = frozenset(
    (
        *ROUTES,
        *API_METHODS,
        *ISSUE_FIELDS,
        *INVOICE_FIELDS,
        *CUSTOMER_FIELDS,
        "frappe",
        "erpnext",
        "softsystem97",
        "Issue",
        "Customer",
        "User",
        "Role",
        "File",
        "Comment",
        "Communication",
        "Contact",
        "Sales Invoice",
        "Issue Priority",
        "Issue Type",
        "ToDo",
        "SS97 Stripe Event",
        "SS97 Ticket Bridge Event",
        "SS97 Client Notification",
        "SS97 Technician",
        "SS97 Technicien",
        "Customer",
        "System Manager",
        "Low",
        "Medium",
        "High",
        "Urgent",
        "Support",
        "API",
        "DocType Event",
        "Link",
        "Dynamic Link",
        "Select",
        "Data",
        "Check",
        "Int",
        "Float",
        "Currency",
        "Date",
        "Datetime",
        "Small Text",
        "Text",
        "Long Text",
        "Text Editor",
        "Read Only",
        "Open",
        "Replied",
        "On Hold",
        "Resolved",
        "Closed",
        "Form",
        "List",
        "Open\nReplied\nOn Hold\nResolved\nClosed",
        "size_limit",
        "read_only",
        "reqd",
        "hidden",
        "options",
        "default",
        "permlevel",
        "depends_on",
        "allow_on_submit",
        "ignore_user_permissions",
        "unavailable",
    )
)


def _file_manifest(root, path):
    root, path = Path(root).resolve(), Path(path).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        return None
    if path.stat().st_size > 2_000_000:
        return {"path": str(path.relative_to(root)), "inspection": "size_limit"}
    return {
        "path": str(path.relative_to(root)),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _symbols(value):
    if isinstance(value, dict):
        return {k: _symbols(v) for k, v in value.items()}
    if isinstance(value, str):
        return value if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", value) else None
    if isinstance(value, (tuple, list)):
        return [_symbols(v) for v in value]
    return None


def _expurgate(value):
    """Allowlist public constants; alias every other string/key with a one-use HMAC.

    No alias map or salt is returned or persisted. Identity equality is preserved
    within this report only; arbitrary metadata names can contain secrets/PII.
    """
    salt = secrets.token_bytes(32)

    def alias(text):
        return "ref_" + hmac.new(salt, text.encode(), hashlib.sha256).hexdigest()[:24]

    def scrub(item, key=None):
        if item is None or type(item) in (bool, int):
            return item
        if isinstance(item, str):
            if item in PUBLIC_VALUES:
                return item
            if key == "version" and re.fullmatch(
                r"\d+\.\d+\.\d+(?:[a-zA-Z0-9.+-]{0,24})?", item
            ):
                return item
            return alias(item)
        if isinstance(item, dict):
            return {
                (k if k in PUBLIC_KEYS or k in PUBLIC_VALUES else alias(str(k))): scrub(
                    v, k
                )
                for k, v in item.items()
            }
        if isinstance(item, (list, tuple)):
            return [scrub(v) for v in item]
        return None

    return scrub(value)


def collect():
    """Admin console only, metadata reads; output is safe-by-default, not whitelisted."""
    frappe.only_for("System Manager")
    data = {
        "executed_route": False,
        "source_exported": False,
        "routes": list(ROUTES),
        "apps": [],
        "hooks": {},
        "workflows": [],
    }
    for app in frappe.get_installed_apps():
        root = Path(frappe.get_app_path(app))
        candidates = []
        for route in ROUTES:
            for stem in (route, route.replace("-", "_")):
                for suffix in (".py", ".html", ".md", "/index.py", "/index.html"):
                    item = _file_manifest(root, root / "www" / (stem + suffix))
                    if item and item not in candidates:
                        candidates.append(item)
        try:
            version = metadata.version(app)
        except metadata.PackageNotFoundError:
            version = "unavailable"
        data["apps"].append(
            {"app": app, "version": version, "route_file_candidates": candidates}
        )
    for hook in (
        "website_path_resolver",
        "page_renderer",
        "permission_query_conditions",
        "has_permission",
        "doc_events",
    ):
        value = frappe.get_hooks(hook)
        if isinstance(value, dict) and hook in (
            "permission_query_conditions",
            "has_permission",
            "doc_events",
        ):
            value = {key: val for key, val in value.items() if key in ("Issue", "*")}
        data["hooks"][hook] = _symbols(value)
    data["rewrite_rule_count"] = len(frappe.get_hooks("website_route_rules") or [])
    data["web_pages"] = frappe.get_all(
        "Web Page",
        filters={"route": ["in", list(ROUTES)]},
        fields=["name", "route", "published", "content_type"],
    )
    meta = frappe.get_meta("Issue")
    data["issue_fields"] = {
        name: (
            {
                key: field.get(key)
                for key in ("fieldtype", "options", "permlevel", "read_only", "reqd")
            }
            if (field := meta.get_field(name))
            else None
        )
        for name in ISSUE_FIELDS
    }
    for key, dt, names in (
        ("invoice_fields", "Sales Invoice", INVOICE_FIELDS),
        ("customer_fields", "Customer", CUSTOMER_FIELDS),
    ):
        target = frappe.get_meta(dt)
        data[key] = {
            name: (
                {
                    attr: field.get(attr)
                    for attr in (
                        "fieldtype",
                        "options",
                        "permlevel",
                        "read_only",
                        "reqd",
                    )
                }
                if (field := target.get_field(name))
                else None
            )
            for name in names
        }
    fields = [
        "role",
        "permlevel",
        "read",
        "write",
        "create",
        "delete",
        "submit",
        "cancel",
        "if_owner",
    ]
    data["issue_permissions"] = [
        {key: row.get(key) for key in fields} for row in meta.permissions
    ]
    data["custom_permissions"] = frappe.get_all(
        "Custom DocPerm", filters={"parent": "Issue"}, fields=fields
    )
    data["technician_roles"] = frappe.get_all(
        "Role",
        filters={"name": ["in", ["SS97 Technician", "SS97 Technicien"]]},
        fields=["name", "disabled", "desk_access"],
    )
    for name in frappe.get_all(
        "Workflow", filters={"document_type": "Issue"}, pluck="name"
    ):
        doc = frappe.get_doc("Workflow", name)
        data["workflows"].append(
            {
                "name": name,
                "active": doc.is_active,
                "state_field": doc.workflow_state_field,
                "states": [
                    {key: row.get(key) for key in ("state", "doc_status", "allow_edit")}
                    for row in doc.states
                ],
                "transitions": [
                    {
                        **{
                            key: row.get(key)
                            for key in ("state", "action", "next_state", "allowed")
                        },
                        "has_private_condition": bool(row.get("condition")),
                    }
                    for row in doc.transitions
                ],
            }
        )
    data["issue_server_scripts"] = frappe.get_all(
        "Server Script",
        filters={"reference_doctype": "Issue"},
        fields=["name", "script_type", "disabled", "doctype_event"],
    )
    data["api_scripts"] = frappe.get_all(
        "Server Script",
        filters={"api_method": ["in", list(API_METHODS)]},
        fields=["name", "api_method", "disabled", "allow_guest"],
    )
    data["client_scripts"] = frappe.get_all(
        "Client Script",
        filters={"dt": "Issue"},
        fields=["name", "dt", "view", "enabled"],
    )
    # Never fetch assignment users, private expressions, setter values or defaults.
    data["assignment_rules"] = frappe.get_all(
        "Assignment Rule",
        filters={"document_type": "Issue"},
        fields=["name", "document_type", "disabled", "priority", "rule", "field"],
    )
    data["property_setters"] = frappe.get_all(
        "Property Setter",
        filters={"doc_type": ["in", ["Issue", "Sales Invoice", "Customer"]]},
        fields=[
            "name",
            "doc_type",
            "doctype_or_field",
            "field_name",
            "property",
            "property_type",
        ],
    )
    data["required_doctypes"] = {
        dt: bool(frappe.db.exists("DocType", dt))
        for dt in (
            "Issue",
            "Customer",
            "User",
            "ToDo",
            "Sales Invoice",
            "SS97 Stripe Event",
            "SS97 Ticket Bridge Event",
            "SS97 Client Notification",
        )
    }
    data["reference_records"] = {
        "issue_priority": {
            name: bool(frappe.db.exists("Issue Priority", name))
            for name in ("Low", "Medium", "High", "Urgent")
        },
        "support_type": bool(frappe.db.exists("Issue Type", "Support")),
    }
    data["custom_field_count"] = frappe.db.count("Custom Field", {"dt": "Issue"})
    data["property_setter_count"] = frappe.db.count(
        "Property Setter", {"doc_type": "Issue"}
    )
    data["user_permission_count"] = frappe.db.count(
        "User Permission", {"allow": "Issue"}
    )
    result = _expurgate(data)
    result["format"] = "ss97-route-metadata-v2"
    result["privacy"] = {"pseudonymized": True, "aliases_stable_across_reports": False}
    result["limits"] = [
        "Metadata only; no source, business records, accounts, secrets or conditions exported",
        "Custom identities are one-report aliases; administrator must review matching sources privately",
        "Routes, sessions, payment, notifications and business workflow not executed",
        "Assignment users/expressions and Property Setter values/defaults not collected; effective targeted fields are reported",
    ]
    return result
