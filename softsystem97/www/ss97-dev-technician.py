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
    context.no_cache = 1
    context.title = 'Interventions — développement'
    context.is_guest = frappe.session.user == 'Guest'
    # Every API call rechecks role/enabled/scope; the HTML is not an authorization boundary.
    return context
