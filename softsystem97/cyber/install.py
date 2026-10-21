"""Explicit administrative role preparation. Never grants roles to any user."""

import frappe

ROLES = (
    "SS97 Cyber Direction",
    "SS97 Cyber Manager",
    "SS97 Cyber Technician",
    "SS97 Cyber Client",
)


def prepare(dry_run=True):
    frappe.only_for("System Manager")
    missing = [role for role in ROLES if not frappe.db.exists("Role", role)]
    if dry_run is False:
        for role in missing:
            frappe.get_doc(
                {
                    "doctype": "Role",
                    "role_name": role,
                    "desk_access": int(role != "SS97 Cyber Client"),
                }
            ).insert()
    return {
        "dry_run": dry_run is not False,
        "missing": missing,
        "users_modified": False,
    }
