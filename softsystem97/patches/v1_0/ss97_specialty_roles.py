"""Install the three SS97 technician specialty roles without granting access.

These names are referenced by the guarded Technician OS lifecycle. Creating
the Role records alone does not activate candidates, grant Desk access, or
assign Role permissions to any DocType.
"""

import frappe

from softsystem97.technician_os.rules import TRACK_ROLES


def execute():
    for role_name in sorted(TRACK_ROLES):
        if frappe.db.exists("Role", role_name):
            continue
        frappe.get_doc({
            "doctype": "Role", "role_name": role_name,
            "desk_access": 0, "is_custom": 1,
        }).insert(ignore_permissions=True)
