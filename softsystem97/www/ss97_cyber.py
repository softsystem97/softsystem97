import frappe

from softsystem97.cyber.permissions import CLIENT, DIRECTORS, TECH, roles

no_cache = 1


def get_context(context):
    if not (
        roles() & (DIRECTORS | {TECH, CLIENT}) or frappe.session.user == "Administrator"
    ):
        frappe.throw("Cyber authorization required", frappe.PermissionError)
    from frappe.sessions import get_csrf_token

    get_csrf_token()  # Persist native CSRF before the first browser mutation.
    context.no_cache = 1
