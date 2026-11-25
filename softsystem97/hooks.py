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
        "validate": [
            "softsystem97.integrations.ticket_bridge.payment_gate.validate_paid_issue",
            "softsystem97.integrations.ticket_bridge.cockpit_completion.validate_pilot_issue",
        ],
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
}

# Pending-only cleanup. No remote engine is controlled by this V1 scheduler.
scheduler_events = {
    "cron": {
        "*/5 * * * *": [
            "softsystem97.integrations.ticket_bridge.dispatch_scheduler.run_pending",
        ],
    },
    "all": ["softsystem97.remote.api.expire_pending_sessions"],
}


# SS97 N2 commercial route adapters.
# Backend authorization remains mandatory.
website_route_rules = [
    {
        "from_route": "/espace-technicien/cockpit-n2",
        "to_route": "ss97-n2-cockpit-pilot",
    },
    {
        "from_route": "/administration-n2/interventions",
        "to_route": "ss97-n2-admin-pilot",
    },
]
