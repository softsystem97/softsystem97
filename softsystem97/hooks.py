# -*- coding: utf-8 -*-
"""SoftSystem97 — app Frappe (Stripe webhook, portail, notifications)."""
from __future__ import annotations

app_name = "softsystem97"
app_title = "SoftSystem97"
app_publisher = "SoftSystem97"
app_description = "Portail client commercial, Stripe webhook, notifications, finance"
app_email = "contact@softsystem97.com"
app_license = "MIT"
app_version = "1.0.0"

required_apps = ["erpnext"]
after_install = "softsystem97.patches.v1_0.stripe_accounting.execute"

# Keep password fields readable throughout the SS97 public/technician portals
# and ERPNext Desk, regardless of the surrounding light or dark theme.
# The visibility control is web-only: Desk already has native password widgets.
web_include_css = [
    "/assets/softsystem97/css/password-contrast.css",
    "/assets/softsystem97/css/portal-contrast.css",
]
web_include_js = [
    "/assets/softsystem97/js/password-visibility.js",
    # Explicit session check for the technician website, including Website Users.
    "/assets/softsystem97/js/technician_session_auth.js",
]
app_include_css = ["/assets/softsystem97/css/password-contrast.css"]

permission_query_conditions = {
	"SS97 Client Notification": "softsystem97.portal.notifications.get_permission_query_conditions",
}
has_permission = {
	"SS97 Client Notification": "softsystem97.portal.notifications.has_permission",
}

# --- API publique (whitelist) ---
# Stripe webhook (POST, guest) :
#   /api/method/softsystem97.integrations.stripe.webhook.stripe_webhook
#   /api/method/softsystem97.integrations.stripe.webhook.webhook
#
# Portail notifications :
#   softsystem97.portal.notifications.get_my_notifications
#   softsystem97.portal.notifications.mark_read
#   softsystem97.portal.notifications.mark_all_read
#   softsystem97.portal.notifications.delete_notification
#
# Portail finance :
#   softsystem97.portal.finance.get_my_finance_kpis
#   softsystem97.portal.finance.get_my_invoices
#   softsystem97.portal.finance.get_my_contracts
#   softsystem97.portal.finance.get_my_quotations
#
# Portail contrats :
#   softsystem97.portal.contracts.list_my_contracts
#   softsystem97.portal.contracts.get_contract
#   softsystem97.portal.contracts.sign_contract
#   softsystem97.portal.contracts.refuse_contract
#   softsystem97.portal.contracts.request_modification

fixtures = [
	{
		"dt": "Role",
		"filters": [["name", "in", ["Customer", "Accounts Manager"]]],
	},
]

# Permissions portail : les APIs whitelist filtrent strictement par frappe.session.user.

# Only revokes existing bridge approvals; never creates an assignment/grant.
doc_events = {
    "Issue": {
        "validate": "softsystem97.integrations.ticket_bridge.payment_gate.validate_paid_issue",
        # Revocation only; never creates a remote connection.
        "on_update": "softsystem97.remote.lifecycle.revoke_on_issue_close",
    },
    "ToDo": {
        "on_update": [
            "softsystem97.integrations.ticket_bridge.policy.revoke_changed_assignment",
            "softsystem97.remote.lifecycle.revoke_on_todo_change",
        ],
        "on_trash": [
            "softsystem97.integrations.ticket_bridge.policy.revoke_changed_assignment",
            "softsystem97.remote.lifecycle.revoke_on_todo_change",
        ],
    },
    "SS97 Technician Mission": {
        "on_update": "softsystem97.remote.lifecycle.revoke_on_mission_change",
    },
    "SS97 Technician Profile": {
        "on_update": "softsystem97.remote.lifecycle.revoke_on_profile_change",
    },
}

# Remote assistance is opt-in; expiry only affects unconnected invitations.
scheduler_events = {
    "all": ["softsystem97.remote.api.expire_pending_sessions"],
}
