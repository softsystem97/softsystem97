"""Permission-safe, session-bound authentication for SS97 technician pages.

This endpoint only identifies the *current* logged-in user. It does not grant
roles, assign work, or authorize individual tickets/remote access operations.
"""

import frappe
from softsystem97.technician_os.rules import TRACKS, TRACK_ROLES


TECHNICIAN_ROLES = ("SS97 Technician", "SS97 Support", "SS97 Tech Lead")
ADMIN_ROLES = ("System Manager", "SS97 Administrator", "SS97 Admin")
PROFILE = "SS97 Technician Profile"


def _active_specialty_profile(user, roles, disabled):
    """N2/N3/N4 are admitted only after the complete reviewed lifecycle.

    A specialty Role by itself is not proof of certification, and a suspended
    profile must never be made operational by an older portal client script.
    """
    config = frappe.conf.get("ss97_tech_os") or {}
    if not isinstance(config, dict) or config.get("enabled") is not True:
        return False
    assigned = set(roles) & TRACK_ROLES
    if len(assigned) != 1 or assigned & set(disabled) or not frappe.db.table_exists(PROFILE):
        return False
    profile = frappe.db.get_value(
        PROFILE, {"candidate_user": user}, ["track", "state", "engagement"], as_dict=True
    )
    return bool(profile and profile.get("track") in TRACKS
                and profile.get("state") == "ACTIVE"
                and profile.get("engagement") == "FREELANCE"
                and TRACKS[profile["track"]]["role"] in assigned)


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
    relevant = [role for role in (*TECHNICIAN_ROLES, *sorted(TRACK_ROLES)) if role in roles]
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
    # Dedicated specialty roles must match an active profile exactly. A user
    # cannot bypass this requirement by also retaining a legacy generic role.
    if roles & TRACK_ROLES:
        result["isTechnician"] = _active_specialty_profile(user, roles, disabled)
    result["user"] = user
    result["fullName"] = frappe.db.get_value("User", user, "full_name") or user
    return result
