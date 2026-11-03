"""Explicit operator tools. Not registered as hooks/patches or HTTP endpoints."""
import frappe

TECHNICIAN_ROLE = 'SS97 Technicien'


def role_inventory():
    frappe.only_for('System Manager')
    return frappe.get_list('Role', fields=['name', 'disabled', 'desk_access'],
                           order_by='name', limit_page_length=0)


def prepare_technician_role(role_name=TECHNICIAN_ROLE, dry_run=True, policy_confirmed=False):
    """Idempotent role-only provisioning; never assigns users or broad DocPerm."""
    frappe.only_for('System Manager')
    if type(dry_run) is not bool or type(policy_confirmed) is not bool:
        frappe.throw('dry_run and policy_confirmed must be JSON booleans')
    if not isinstance(role_name, str) or not role_name.strip():
        frappe.throw('A confirmed role name is required')
    role_name = role_name.strip()
    if role_name.casefold() in {'system manager', 'administrator', 'candidat ss97', 'all', 'guest'}:
        frappe.throw('This role cannot be used as the technician role')
    existing = frappe.db.get_value('Role', role_name,
                                  ['name', 'disabled', 'desk_access'], as_dict=True)
    result = dict(role_name=role_name, exists=existing is not None, changed=False,
                  dry_run=dry_run, existing=existing, ticket_permissions_configured=False,
                  portal_authorization_verified=False)
    if existing is not None:
        return result  # Preserve disabled, Desk and all existing permission settings.
    if dry_run:
        result['proposed'] = dict(role_name=role_name, desk_access=0, is_custom=1)
        return result
    if not policy_confirmed:
        frappe.throw('Confirm the real portal role policy and authorize this operation first')
    frappe.get_doc(dict(doctype='Role', role_name=role_name,
                        desk_access=0, is_custom=1)).insert()
    result.update(exists=True, changed=True)
    return result  # Transaction owned by the operator/runner; no early commit.


def plan_existing_user(user, desired_last_name=None):
    """Read-only plan: never recreate, rename the login, save or reset a password."""
    frappe.only_for('System Manager')
    account = frappe.db.get_value('User', user,
                                  ['first_name', 'last_name', 'enabled', 'user_type'], as_dict=True)
    if account is None:
        frappe.throw('Existing user not found; no account was created', frappe.DoesNotExistError)
    changes = {}
    if desired_last_name is not None:
        if not isinstance(desired_last_name, str) or not desired_last_name.strip():
            frappe.throw('A nonempty last name is required')
        if account.last_name != desired_last_name.strip():
            changes['last_name'] = desired_last_name.strip()
    return dict(account=account, current_roles=frappe.get_roles(user), proposed_changes=changes,
                applied=False, role_assignment_prepared=False, portal_policy_confirmed=False)
