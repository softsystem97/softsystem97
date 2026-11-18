"""New independent Intelligence 360 website route; existing portal remains intact."""
import frappe

no_cache = True


def get_context(context):
    context.title = "Soft System 97 — Intelligence 360"
    context.no_cache = 1
    context.is_guest = frappe.session.user == "Guest"
    if not context.is_guest:
        from frappe.sessions import get_csrf_token
        get_csrf_token()
    return context
