# -*- coding: utf-8 -*-
"""Résolution Customer ↔ utilisateur portail."""
from __future__ import annotations

import frappe
from frappe import _


def resolve_customer_for_user(user: str | None = None, customer_param: str | None = None) -> str | None:
	"""Retourne le Customer lié à l'utilisateur session, ou None."""
	user = user or frappe.session.user
	if not user or user == "Guest":
		return None

	roles = set(frappe.get_roles(user))
	is_staff = bool(roles & {"System Manager", "Accounts Manager"})

	if customer_param and is_staff:
		if frappe.db.exists("Customer", customer_param):
			return customer_param
		return None

	if is_staff and not customer_param:
		return None

	# Portal User → Customer
	portal_customer = frappe.db.get_value("Portal User", {"user": user}, "parent")
	if portal_customer and frappe.db.exists("Customer", portal_customer):
		return portal_customer

	# Contact email → Customer (via Dynamic Link)
	email = frappe.db.get_value("User", user, "email")
	if email:
		contacts = frappe.get_all(
			"Contact Email",
			filters={"email_id": email},
			pluck="parent",
			limit=20,
		)
		for contact in contacts:
			links = frappe.get_all(
				"Dynamic Link",
				filters={
					"parenttype": "Contact",
					"parent": contact,
					"link_doctype": "Customer",
				},
				pluck="link_name",
				limit=1,
			)
			if links:
				return links[0]

		# Customer.email_id direct
		direct = frappe.db.get_value("Customer", {"email_id": email}, "name")
		if direct:
			return direct

	return None


def require_customer(user: str | None = None, customer_param: str | None = None) -> str:
	customer = resolve_customer_for_user(user, customer_param)
	if not customer:
		frappe.throw(_("Aucun client associé à votre compte."), frappe.PermissionError)
	return customer


@frappe.whitelist()
def get_my_customer(customer: str | None = None) -> dict:
	"""API portail : Customer lié à la session (jamais un autre client)."""
	cust = resolve_customer_for_user(frappe.session.user, customer)
	if not cust:
		return {"customer": None, "name": None}
	return {"customer": cust, "name": cust}
