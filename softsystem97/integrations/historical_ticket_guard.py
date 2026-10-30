"""HTTP write gate for the imported client Server Script (no ticket grants)."""

import frappe


@frappe.whitelist(methods=["POST"])
def require_write_session():
    # Explicit check also protects calls made through the Server Script dispatcher.
    request = getattr(frappe.local, "request", None)
    user = frappe.session.user
    if (
        not request
        or request.method != "POST"
        or not user
        or user == "Guest"
        or not frappe.db.get_value("User", user, "enabled")
    ):
        frappe.throw("Session active et requête POST requises.", frappe.PermissionError)
    return True


@frappe.whitelist(methods=["POST"])
def require_cockpit_session(issue_name, action):
    """Gate the recovered cockpit through scoped approvals and a bound business decision.

    No legacy payment marker, JavaScript role or unassigned Issue grants access.
    Disabled bridge, unverified metadata or missing business provider deny access.
    """
    from softsystem97.integrations.ticket_bridge import api, historical, policy

    require_write_session()
    targets = {
        "start": "Intervention en cours",
        "pause": "Intervention en pause",
        "resume": "Intervention en cours",
        "complete": "Intervention terminée",
        "submit_close": "Validation administrateur en attente",
        "admin_clear_security": "Intervention en pause",
        "close_remote": "Intervention en cours",
        "gwen_emit": "",
    }
    if (
        not isinstance(action, str)
        or action not in targets
        or not isinstance(issue_name, str)
        or not 1 <= len(issue_name) <= 140
    ):
        frappe.throw("Action cockpit invalide.", frappe.PermissionError)
    policy.settings()
    if not historical.enabled():
        frappe.throw(
            "Compatibilité historique et fournisseur métier requis.",
            frappe.PermissionError,
        )
    doc = api._issue(issue_name, lock=True)
    if action == "admin_clear_security":
        policy.dispatcher()
        doc.check_permission("write")
    elif action == "close_remote" and policy.client_customer_for_user(
        frappe.session.user
    ):
        policy.authorize(doc, "client")
    else:
        policy.authorize(doc, "technician")
    historical.require_authorization(
        "cockpit." + action,
        doc,
        technician=frappe.session.user,
        target_status=targets[action],
    )
    return True
