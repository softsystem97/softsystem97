"""Permission-safe, session-bound authentication for SS97 technician pages.

This endpoint only identifies the *current* logged-in user. It does not grant
roles, assign work, or authorize individual tickets/remote access operations.
"""

import frappe


TECHNICIAN_ROLES = ("SS97 Technician", "SS97 Support", "SS97 Tech Lead")
ADMIN_ROLES = ("System Manager", "SS97 Administrator", "SS97 Admin")


def evaluate_technician_session(user, enabled, assigned_roles, disabled_roles=()):
    """Fail closed for guest, disabled user, absent or disabled roles."""
    if not user or user == "Guest" or not enabled:
        return {"authenticated": False, "isTechnician": False, "isAdmin": False}
    roles = set(assigned_roles or ())
    disabled = set(disabled_roles or ())
    return {
        "authenticated": True,
        "isTechnician": any(role in roles and role not in disabled for role in TECHNICIAN_ROLES),
        "isAdmin": user == "Administrator" or any(role in roles for role in ADMIN_ROLES),
    }


@frappe.whitelist(allow_guest=False)
def my_technician_access():
    """Return current-session status without looking up any other user's data."""
    user = frappe.session.user
    if not user or user == "Guest":
        return evaluate_technician_session("Guest", False, ())
    enabled = frappe.db.get_value("User", user, "enabled")
    if not enabled:
        return evaluate_technician_session(user, False, ())

    roles = set(frappe.get_roles(user))
    relevant = [role for role in TECHNICIAN_ROLES if role in roles]
    disabled = set()
    if relevant:
        role_rows = frappe.get_all(
            "Role",
            filters={"name": ["in", relevant]},
            fields=["name", "disabled"],
            limit_page_length=len(relevant),
        )
        existing = {row["name"] for row in role_rows}
        disabled = (set(relevant) - existing) | {
            row["name"] for row in role_rows if row.get("disabled")
        }

    result = evaluate_technician_session(user, enabled, roles, disabled)
    result["user"] = user
    result["fullName"] = frappe.db.get_value("User", user, "full_name") or user
    return result
