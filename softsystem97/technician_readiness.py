"""Read-only N2 technician access preflight for an authorized administrator.

The production Web Pages and technician profile rules may live outside this
repository.  A matching role is necessary, but never sufficient, to grant
access.  This module never creates a User, grants a role or exposes secrets.
"""

import frappe


HISTORICAL_ROLE = "SS97 Technician"
BRIDGE_ROLE = "SS97 Technicien"


def evaluate_access(account, held_roles, role_rows):
    """Pure diagnosis, deliberately unable to declare the live portal ready."""
    roles = set(held_roles or ())
    existing = {row["name"]: row for row in role_rows}
    canonical = existing.get(HISTORICAL_ROLE)
    blockers = []
    if account is None:
        blockers.append("USER_MISSING")
    elif not account.get("enabled"):
        blockers.append("USER_DISABLED")
    if canonical is None:
        blockers.append("HISTORICAL_ROLE_MISSING")
    elif canonical.get("disabled"):
        blockers.append("HISTORICAL_ROLE_DISABLED")
    if HISTORICAL_ROLE not in roles:
        blockers.append("HISTORICAL_ROLE_NOT_ASSIGNED")

    return {
        "state": "BLOCKED" if blockers else "ROLE_CHECKS_PASSED_PROFILE_UNVERIFIED",
        "blockers": blockers,
        "historical_role": HISTORICAL_ROLE,
        "historical_role_assigned": HISTORICAL_ROLE in roles,
        "historical_role_active": canonical is not None and not bool(canonical.get("disabled")),
        "bridge_role": BRIDGE_ROLE,
        "bridge_role_assigned": BRIDGE_ROLE in roles,
        "account_enabled": bool(account and account.get("enabled")),
        "portal_source_reviewed": False,
        "technician_profile_verified": False,
        "browser_login_verified": False,
        "remote_desktop_verified": False,
    }


def administrator_n2_access_report(user):
    """Inspect exactly one account in bench console; not a public API."""
    frappe.only_for("System Manager")
    if not isinstance(user, str) or not user.strip() or len(user) > 140:
        frappe.throw("Identifiant utilisateur invalide.")
    user = user.strip()
    account = frappe.db.get_value("User", user, ["enabled"], as_dict=True)
    roles = frappe.get_roles(user) if account is not None else []
    role_rows = frappe.get_all(
        "Role",
        filters={"name": ["in", [HISTORICAL_ROLE, BRIDGE_ROLE]]},
        fields=["name", "disabled"],
        limit_page_length=2,
    )
    return evaluate_access(account, roles, role_rows)
