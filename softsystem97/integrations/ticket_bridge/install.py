"""Explicit console-only preparation: no migration hook, grants or user changes."""
import frappe
from softsystem97.provisioning import prepare_technician_role


def prepare(dry_run=True, compatibility_confirmed=False, role_name='SS97 Technicien'):
    frappe.only_for('System Manager')
    role = prepare_technician_role(role_name, dry_run=dry_run,
                                  policy_confirmed=compatibility_confirmed)
    permissions = []
    for dt in ['DocPerm', 'Custom DocPerm']:
        permissions.extend(frappe.get_all(dt, filters={'role': role_name, 'parent': 'Issue'},
            fields=['parent', 'read', 'write', 'create', 'delete', 'share', 'if_owner']))
    return {'role': role, 'issue_permissions_added': [], 'existing_issue_permissions': permissions,
            'users_changed': False, 'enabled': False,
            'authorization': 'Scoped service APIs; native Issue/ToDo; no global Issue grants',
            'review_existing_permissions_before_activation': bool(permissions)}
