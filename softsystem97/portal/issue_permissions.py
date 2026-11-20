"""Restrict native Issue access for SS97 technicians to approved assignments.

The stock Frappe ToDo assignment alone is not proof of administrative approval:
assignees may create or retarget their own ToDos. The bridge's protected Event
receipt binds the exact ToDo, Issue and technician. Other roles retain their
existing ERPNext permission model; this hook cannot grant any new capability.
"""

import frappe

from softsystem97.integrations.ticket_bridge import historical, policy
from softsystem97.technician_os.rules import TRACK_ROLES


SCOPED_ROLES = {"SS97 Technician", *TRACK_ROLES}
PRIVILEGED_ROLES = {"System Manager", "SS97 Administrator", "SS97 Admin", "SS97 Tech Lead"}
EVENT = "SS97 Ticket Bridge Event"


def _scoped(user):
    if not user or user in {"Guest", "Administrator"}:
        return False
    roles = set(frappe.get_roles(user))
    return bool(roles & SCOPED_ROLES) and not bool(roles & PRIVILEGED_ROLES)


def _approval_schema_ready():
    """Fail closed on disabled/incomplete bridges, never trust legacy ToDo alone."""
    config = frappe.conf.get("ss97_ticket_bridge") or {}
    if not isinstance(config, dict) or config.get("enabled") is not True:
        return False
    if not frappe.db.table_exists(EVENT):
        return False
    meta = frappe.get_meta(EVENT)
    if not all(meta.has_field(field) for field in ("assignment", "technician", "revoked", "response_json", "issue", "action")):
        return False
    if historical.enabled() and not frappe.get_meta("Issue").has_field("ss97_technician"):
        return False
    return True


def get_permission_query_conditions(user=None):
    user = user or frappe.session.user
    if not _scoped(user):
        return ""
    if not _approval_schema_ready():
        return "1=0"
    # The quoted user is safe inside the SQL fragment required by Frappe's hook.
    return ("EXISTS (SELECT 1 " + policy.approved_assignment_query()
            + " AND t.reference_name = `tabIssue`.`name`"
            + " AND t.allocated_to = " + frappe.db.escape(user) + ")")


def has_permission(doc, ptype=None, user=None):
    user = user or frappe.session.user
    if not _scoped(user):
        return None  # Default Frappe permissions for clients and staff.
    if not _approval_schema_ready():
        return False
    # An approved assignment only removes our extra restriction; ERPNext's
    # native DocPerm must still independently allow the requested operation.
    return None if policy.assigned(doc.name, user) else False
