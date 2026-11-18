"""Separate development route; never takes over the historical technician URL."""
import frappe
from softsystem97.integrations.ticket_bridge.policy import settings

no_cache = True


def get_context(context):
    try:
        settings()
    except frappe.PermissionError:
        frappe.local.message_log = []
        raise frappe.DoesNotExistError('Page indisponible')
    if frappe.session.user != 'Guest':
        from frappe.sessions import get_csrf_token
        get_csrf_token()  # Persist native session CSRF before rendering a form.
    context.no_cache = 1
    context.title = 'Interventions — développement'
    context.is_guest = frappe.session.user == 'Guest'
    # Every API call rechecks role/enabled/scope; the HTML is not an authorization boundary.
    return context
