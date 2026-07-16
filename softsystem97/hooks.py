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
