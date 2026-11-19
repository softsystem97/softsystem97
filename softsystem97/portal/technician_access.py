"""Session-bound technician access for the public website.

The public login/dashboard must not query other Users' roles or depend on
list permission for Technician Application / Employee.  Only Frappe's server
session determines the identity.  All business APIs retain their own checks.
"""

import frappe


TECHNICIAN_ROLES = ("SS97 Technician", "SS97 Support", "SS97 Tech Lead")
ADMIN_ROLES = ("System Manager", "Administrator", "SS97 Administrator", "SS97 Admin")


def evaluate_technician_session(user, enabled, assigned_roles, disabled_roles):
    """Pure, conservative access decision; never grants a role."""
    if not user or user == "Guest" or not enabled:
        return {"authenticated": False, "isTechnician": False, "isAdmin": False}

    assigned = set(assigned_roles or ())
    disabled = set(disabled_roles or ())
    has_tech_role = any(role in assigned and role not in disabled for role in TECHNICIAN_ROLES)
    has_admin_role = user == "Administrator" or any(role in assigned for role in ADMIN_ROLES)
    return {
        "authenticated": True,
        "isTechnician": has_tech_role,
        "isAdmin": has_admin_role,
    }


@frappe.whitelist(allow_guest=False)
def my_technician_access():
    """Return ONLY the current session's portal status (no user argument)."""
    user = frappe.session.user
    if not user or user == "Guest":
        return evaluate_technician_session("Guest", False, (), ())

    enabled = frappe.db.get_value("User", user, "enabled")
    if not enabled:
        return evaluate_technician_session(user, False, (), ())

    roles = set(frappe.get_roles(user))
    relevant = tuple(role for role in TECHNICIAN_ROLES if role in roles)
    disabled = set()
    if relevant:
        rows = frappe.get_all(
            "Role", filters={"name": ["in", list(relevant)]},
            fields=["name", "disabled"], limit_page_length=len(relevant),
        )
        valid_names = {row["name"] for row in rows}
        disabled = (set(relevant) - valid_names) | {
            row["name"] for row in rows if row.get("disabled")
        }

    result = evaluate_technician_session(user, enabled, roles, disabled)
    result["user"] = user
    # Server-side lookup of one's own name requires no User-list permission.
    result["fullName"] = frappe.db.get_value("User", user, "full_name") or user
    return result
