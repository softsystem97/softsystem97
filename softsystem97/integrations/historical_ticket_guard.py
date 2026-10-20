"""HTTP write gate for the imported client Server Script (no ticket grants)."""
import frappe


@frappe.whitelist(methods=['POST'])
def require_write_session():
    # Explicit check also protects calls made through the Server Script dispatcher.
    request = getattr(frappe.local, 'request', None)
    user = frappe.session.user
    if (not request or request.method != 'POST' or not user or user == 'Guest'
            or not frappe.db.get_value('User', user, 'enabled')):
        frappe.throw('Session active et requête POST requises.', frappe.PermissionError)
    return True
