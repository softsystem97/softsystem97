# -*- coding: utf-8 -*-
"""API finance portail client (KPIs, factures, contrats, devis)."""
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from softsystem97.portal.customer import resolve_customer_for_user


def _empty_finance() -> dict:
	return {
		"customer": None,
		"kpis": {
			"total_invoiced": 0,
			"total_outstanding": 0,
			"total_paid": 0,
			"open_quotations": 0,
			"active_contracts": 0,
			"currency": "EUR",
		},
		"invoices": [],
		"contracts": [],
		"quotations": [],
	}


@frappe.whitelist()
def get_my_finance_kpis(customer: str | None = None) -> dict:
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Connexion requise."), frappe.PermissionError)

	resolved = resolve_customer_for_user(user, customer)
	if not resolved:
		return _empty_finance()["kpis"]

	invoices = frappe.get_all(
		"Sales Invoice",
		filters={"customer": resolved, "docstatus": 1},
		fields=["grand_total", "outstanding_amount", "currency", "status"],
	)

	currency = invoices[0].currency if invoices else "EUR"
	total_invoiced = sum(flt(i.grand_total) for i in invoices)
	total_outstanding = sum(flt(i.outstanding_amount) for i in invoices)
	total_paid = total_invoiced - total_outstanding

	open_quotations = frappe.db.count(
		"Quotation",
		{"party_name": resolved, "docstatus": 1, "status": ["in", ["Open", "Replied"]]},
	)

	active_contracts = frappe.db.count(
		"Contract",
		{"party_name": resolved, "party_type": "Customer", "is_active": 1},
	)

	return {
		"customer": resolved,
		"total_invoiced": total_invoiced,
		"total_outstanding": total_outstanding,
		"total_paid": total_paid,
		"open_quotations": open_quotations,
		"active_contracts": active_contracts,
		"currency": currency,
	}


@frappe.whitelist()
def get_my_invoices(
	customer: str | None = None,
	limit: int = 50,
	status: str | None = None,
) -> dict:
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Connexion requise."), frappe.PermissionError)

	resolved = resolve_customer_for_user(user, customer)
	if not resolved:
		return {"customer": None, "invoices": []}

	fields = [
		"name",
		"status",
		"grand_total",
		"outstanding_amount",
		"currency",
		"due_date",
		"posting_date",
		"modified",
	]
	meta = frappe.get_meta("Sales Invoice")
	for custom in (
		"ss97_payment_status",
		"ss97_stripe_checkout_url",
		"ss97_receipt_ref",
		"ss97_stripe_mode",
	):
		if meta.has_field(custom):
			fields.append(custom)

	filters: dict = {"customer": resolved, "docstatus": ["!=", 2]}
	if status:
		filters["status"] = status

	rows = frappe.get_all(
		"Sales Invoice",
		filters=filters,
		fields=fields,
		order_by="posting_date desc",
		limit_page_length=int(limit),
	)
	return {"customer": resolved, "invoices": rows}


@frappe.whitelist()
def get_my_contracts(customer: str | None = None, limit: int = 50) -> dict:
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Connexion requise."), frappe.PermissionError)

	resolved = resolve_customer_for_user(user, customer)
	if not resolved:
		return {"customer": None, "contracts": []}

	from softsystem97.portal.contracts import serialize_contract_list

	contracts = serialize_contract_list(resolved, limit=int(limit))
	return {"customer": resolved, "contracts": contracts}


@frappe.whitelist()
def get_my_quotations(customer: str | None = None, limit: int = 50) -> dict:
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Connexion requise."), frappe.PermissionError)

	resolved = resolve_customer_for_user(user, customer)
	if not resolved:
		return {"customer": None, "quotations": []}

	rows = frappe.get_all(
		"Quotation",
		filters={"party_name": resolved, "docstatus": ["!=", 2]},
		fields=[
			"name",
			"status",
			"transaction_date",
			"valid_till",
			"grand_total",
			"currency",
			"modified",
		],
		order_by="transaction_date desc",
		limit_page_length=int(limit),
	)
	return {"customer": resolved, "quotations": rows}
